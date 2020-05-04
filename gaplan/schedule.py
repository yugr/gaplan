# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# This module contains APIs for simple user-controlled time-boxed scheduling.

# This is WIP !!!

from gaplan.common.error import error, error_if, warn
from gaplan.common import matcher as M
from gaplan.common import parse as PA
from gaplan.common import interval as I

import datetime
import sys

class SchedBlock:
  def __init__(self, seq, offset, loc):
    self.seq = seq
    self.offset = offset
    self.loc = loc
    self.blocks = []
    self.alloc = []
    self.deadline = None
    self.duration = None
    self.goal_name = None
    self.parallel = None

  def add_goal(self, name, attrs, loc):
    block = SchedBlock(False, self.offset, loc)
    block.goal_name = name
    block.add_attrs(attrs, loc)
    self.blocks.append(block)

  def add_attrs(self, attrs, loc):
    for a in attrs:
      if a.startswith('@'):
        self.alloc, _ = PA.read_alloc(a)
        continue

      if M.search(r'^[0-9]{4}-', a):
        self.duration = PA.read_date2(a, loc)
        continue

      if a.startswith('||'):
        self.parallel = PA.read_par(a)
        continue

      if not M.search(r'^([a-z_0-9]+)\s*(.*)', a):
        error(loc, "failed to parse block attribute: %s" % a)
      k = M.group(1).strip()
      v = M.group(2).strip()

      if k == 'deadline':
        self.deadline, _ = PA.read_date(v, loc)
        continue

      error(loc, "unknown block attribute '%s'" % k)

  def dump(self, p):
    p.writeln("%s sched block (%s)" % ("Sequential" if self.seq else "Parallel", self.loc))
    with p:
      if self.duration is not None:
        p.writeln("Duration: %s" % self.duration)
      if self.goal_name is not None:
        p.writeln("Goal: " + self.goal_name)
        with p:
          if self.parallel is not None:
            p.writeln("parallelism: %s" % self.parallel)
          if self.alloc:
            p.writeln("alloc: %s" % ', '.join(self.alloc))
      if self.deadline is not None:
        p.writeln("Deadline: %s" % self.deadline)
      for block in self.blocks:
        block.dump(p)

class Schedule:
  def __init__(self, blocks, loc):
    self.blocks = blocks
    self.loc = loc

  def dump(self, p):
    p.writeln("= Schedule at %s =\n" % self.loc)
    p.writeln("Blocks:")
    with p:
      for block in self.blocks:
        block.dump(p)
    p.writeln("")

class HolidayCalendar:
  def __init__(self, holidays):
    self.holidays = I.Seq(holidays)

  def allows_effort(self, iv, effort):
    """Checks whether we have enough working hours in interval of time."""
    ndays = (iv.finish - iv.start).days
    # Fast check
    if ndays * 8 < effort:
      return False, None
    # Slow check
    # TODO: do this faster
    # TODO: hour-based precision
    start = None
    for day in range(ndays):
      d = iv.start + datetime.timedelta(days=day)
      if d.weekday() < 5 and not self.holidays.contains(d):
        if start is None:
          start = d
        effort -= 8
      if effort <= 0:
        return True, I.Interval(start, d, closed=True)
    return False, None

class GoalInfo:
  def __init__(self, name, completion_date):
    self.name = name
    self.completion_date = completion_date

  def dump(self, p):
    p.writeln("%s: %s" % (self.name, self.completion_date))

class ActivityInfo:
  def __init__(self, act, iv, alloc):
    self.act = act
    self.iv = iv
    self.alloc = alloc

  def dump(self, p):
    s = '/'.join([rc.name for rc in self.alloc])
    p.writeln("%s: %s%s" % (self.act.name, self.iv,
                            (" @%s" % s) if s else ""))

class AllocationInfo:
  def __init__(self, rc, holidays):
    self.rc = rc
    self.name = rc.name
    self.sheet = []
    self.cal = HolidayCalendar(holidays + rc.vacations)

  def allocate(self, start, effort, v):
    if not self.sheet:
      self.sheet = [I.Interval(start)]
      ret = self.allocate(start, effort, v)
      self.sheet = []
      return ret

    if v: print("allocate: allocating effort %g @%s from %s" % (effort, self.name, start))

    last_iv = I.Interval(datetime.date(datetime.MAXYEAR, 12, 31))
    for i, (left, right) in enumerate(zip(self.sheet, self.sheet[1:] + [last_iv])):
      if start >= right.start:
        continue
      gap = I.Interval(max(left.finish, start), right.start)
      if v: print("allocate: found free slot %s" % gap)
      ok, iv = self.cal.allows_effort(gap, effort)
      if not ok:
        if v: print("allocate: slot %s rejected due to holidays" % gap)
        continue
      if v: print("allocate: updated due to holidays: %s" % iv)
      fragmentation = iv.start - left.finish
      if gap.finish != sys.maxsize:
        fragmentation += gap.finish - iv.finish
      return i + 1, iv, fragmentation
    assert ""

  def dump(self, p):
    ss = []
    for iv in self.sheet:
      ss.append("%s - %s" % (iv.start, iv.finish))
    p.writeln("%s: %s" % (self.name, ', '.join(ss)))

class Timetable:
  def __init__(self, prj, v):
    self.goals = {}
    self.acts = {}
    self.rcs = {}
    self.v = v
    for rc in prj.members:
      self.rcs[rc.name] = AllocationInfo(rc, prj.holidays)

  def is_completed(self, goal):
    return goal.name in self.goals

  def get_completion_date(self, goal):
    return self.goals[goal.name].completion_date

  def set_completion_date(self, goal, d):
    error_if(self.is_completed(goal), 
             "goal '%s' scheduled more than once" % goal.name)
    self.goals[goal.name] = GoalInfo(goal.name, d)

  def is_done(self, act):
    return act.name in self.acts

  def get_duration(self, act):
    return self.acts[act.name].iv

  def set_duration(self, act, iv, alloc):
    error_if(self.is_done(act), 
             "activity '%s' scheduled more than once" % act.name)
    self.acts[act.name] = ActivityInfo(act, iv, alloc)

  def assign_best_rcs(self, rcs, start, effort, parallel):
    # How many chunks we can split work to?
    n = min(parallel, len(rcs))

    if self.v:
      print("assign_best_rcs: allocate %sh @%s ||%d"
            % (effort, ', '.join(rc.name for rc in rcs), parallel))

    # Find optimal resource count
    best_allocs = best_finish = None
    for i in range(1, n + 1):
      if self.v: print("assign_best_rcs: use ||%d" % i)
      sched_data = []
      e = effort / i
      for rc in rcs:
        rc_info = self.rcs[rc.name]
        rc_effort = e / rc.efficiency
        j, iv, frag = rc_info.allocate(start, rc_effort, self.v)
        sched_data.append((rc.name, j, iv, frag))
      sched_data.sort(key=lambda data: (data[2].finish, data[3]))  # I hate Python...
      finish = max(iv.finish for _1, _2, iv, _4 in sched_data[:i])
      if best_finish is None or finish < best_finish:
        best_allocs = sched_data[:i]
        best_finish = finish
      if self.v:
        print("assign_best_rcs: finishing on %s @%s"
              % (iv.finish, ', '.join(name for name, _2, _3, _4 in sched_date[:i])))

    # We found optimal number of resources so perform allocation
    e = effort / len(best_allocs)
    total_iv = None
    total_rcs = []
    for name, j, iv, _ in best_allocs:
      rc_info = self.rcs[name]
      rc_info.sheet.insert(j, iv)
      total_iv = iv if total_iv is None else total_iv.union(iv)
      total_rcs.append(rc_info.rc)

    return total_iv, total_rcs

  def dump(self, p):
    p.writeln("= Timetable =")

    p.writeln("Scheduled %d goals and %d activities\n"
              % (len(self.goals), len(self.acts)))

    p.writeln("Goals:")
    with p:
      for info in sorted(self.goals.values(), key=lambda i: (i.completion_date, i.name)):
        info.dump(p)
    p.writeln("")

    p.writeln("Activities:")
    with p:
      for info in sorted(self.acts.values(), key=lambda a: a.iv.start):
        info.dump(p)
    p.writeln("")

    p.writeln("Resources:")
    with p:
      for _, info in sorted(self.rcs.items()):
        info.dump(p)

class Scheduler:
  def __init__(self, v=0):
    self.prj = self.net = self.sched = self.table = None
    self.v = v

  def _dbg(self, msg):
    if self.v: print(msg)

  def _compute_time(self, W, alloc, start):
    # We want to detect optimal time to split effort 'W'
    # between 'alloc' engineers, starter no earlier than 'start'.
    # Assuming that engineers will all start at the same time
    #   ts = max(t1, t2, ...)
    # and work for same amount of time 't' we have
    #   W = eff1 * t + eff2 * t + ...
    # and
    #   t = W / (eff1 + eff2 + ...)
    # 
    # TODO: relieve the assumption of uniform 'ts' and 't'
    ts = start
    for a in alloc:
      ts = self.table.get_earliest_after(a.name, ts)
    t = W / sum(a.efficiency for a in alloc)
    return [(ts, t)] * len(alloc)

  def _schedule_goal(self, goal, start, alloc, par, warn_if_past=True):
    self._dbg("_schedule_goal: scheduling goal '%s': start=%s, alloc=%s, par=%s"
              % (goal.name, start, alloc, par))

    if goal.completion_date is not None:
      self._dbg("_schedule_goal: goal already scheduled")
      if warn_if_past and goal.completion_date < start:
        warn(goal.loc, "goal '%s' is completed on %s, before %s"
                       % (goal.name, goal.completion_date, start))
      # TODO: warn if completion_date < start
      self.table.set_completion_date(goal, goal.completion_date)
      return goal.completion_date

    if goal.is_completed():
      warn(goal.loc, "unable to schedule completed goal '%s' with no completion date" % goal.name)
      self.table.set_completion_date(goal, datetime.date.today())
      return datetime.date.today()

    completion_date = start
    goal_alloc = set()
    for act in goal.preds:
      if act.duration is not None:
        # TODO: register spent time for devs
        if warn_if_past and act.duration.start < start:
          warn(act.loc, "activity '%s' started on %s, before %s"
                        % (act.name, act.duration.start, start))
        completion_date = max(completion_date, act.duration.finish)
        continue

      act_start = start
      if act.head is not None:
        if not self.table.is_completed(act.head):
          # For goals that are not specified by schedule we use default settings
          self._dbg("_schedule_goal: scheduling predecessor '%s'" % act.head.name)
          self._schedule_goal(act.head, datetime.date.today(), [], None, warn_if_past=False)
          if not act.overlaps:
            act_start = max(act_start, self.table.get_completion_date(act.head))
          else:
            for pred in self.head.preds:
              overlap = act.overlaps.get(pred.id)
              if overlap is not None:
                pred_iv = selt.table.get_duration(pred)
                span = (pred_iv.finish - pred_iv.start) * (1 - overlap)
                act_start = max(act_start, pred_iv.start + span)

      if act.is_instant():
        completion_date = max(completion_date, act_start)
        continue

      plan_rcs = self.prj.get_resources(act.alloc)
      if alloc:
        rcs = self.prj.get_resources(alloc)
        if any(rc for rc in rcs if rc not in plan_rcs):
          error("allocations defined in schedule (%s) do not match "
                "allocations defined in action (%s)"
                % ('/'.join(alloc), '/'.join(rc.name for rc in plan_rcs)))
      else:
        rcs = plan_rcs

      act_par = par
      if act_par is None:
        act_par = act.parallel

      act_effort, _ = act.estimate()
      act_effort *= 1 - act.completion

      self._dbg("_schedule_goal: scheduling activity %s: start=%s, effort=%s, par=%s, rcs=%s"
                % (act.name, act_start, act_effort, act_par, ', '.join(rc.name for rc in rcs)))

      iv, assigned_rcs = self.table.assign_best_rcs(rcs, act_start, act_effort, act_par)
      self._dbg("_schedule_goal: assignment for activity %s: @%s, duration %s"
                % (act.name, ', '.join(rc.name for rc in assigned_rcs), iv))

      self.table.set_duration(act, iv, assigned_rcs)
      completion_date = max(completion_date, iv.finish)

    self.table.set_completion_date(goal, completion_date)

    return completion_date

  def _schedule_block(self, block, start, alloc, par):
    self._dbg("_schedule_block: scheduling block in %s: start=%s, alloc=%s, par=%s"
              % (block.loc, start, alloc, par))

    alloc = block.alloc or alloc
    par = block.parallel or par
    latest = start

    if block.goal_name is None:
      for b in block.blocks:
        last = self._schedule_block(b, start, alloc, par)
        latest = max(latest or last, last)
        if block.seq:
          start = last
    else:
      assert not block.blocks, "block with goals should have no subblocks"
      goal = self.net.name_to_goal.get(block.goal_name)
      error_if(goal is None, block.loc, "goal '%s' not found in plan" % block.goal_name)
      goal_finish = self._schedule_goal(goal, start, alloc, par)
      latest = max(latest, goal_finish)

    if block.deadline is not None and latest > block.deadline:
      warn("Failed to schedule block at %s before deadline %s"
           % (block.loc, block.deadline))

    return latest

  def schedule(self, prj, net, sched):
    self.prj = prj
    self.net = net
    self.sched = sched
    self.table = Timetable(prj, self.v)
    for block in sched.blocks:
      self._schedule_block(block, datetime.date.today(), [], None)
    return self.table
