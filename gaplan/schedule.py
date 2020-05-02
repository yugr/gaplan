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
  def __init__(self, par, offset, loc):
    self.par = par
    self.offset = offset
    self.loc = loc
    self.alloc = []
    self.duration = None
    self.goal_name = None
    self.deadline = None
    self.blocks = []

  def add_goal(self, goal_name, loc):
    block = SchedBlock(False, self.offset, loc)
    block.goal_name = goal_name
    self.blocks.append(block)

  def add_attrs(self, attrs, loc):
    for a in attrs:
      if M.search(r'^@\s*(.*)', a):
        self.alloc = M.group(1).split('/')
        continue

      if M.search(r'^[0-9]{4}-', a):
        self.duration = PA.read_date2(a, loc)
        continue

      if not M.search(r'^([a-z_0-9]+)\s*(.*)', a):
        error(loc, "failed to parse block attribute: %s" % a)

      k = M.group(1)
      v = M.group(2)
      if k == 'deadline':
        self.deadline, _ = PA.read_date(v, loc)
      else:
        error(loc, "unknown block attribute '%s'" % k)

  def dump(self, p):
    p.writeln("%s sched block (%s)" % ("Parallel" if self.par else "Sequential", self.loc))
    with p:
      if self.duration is not None:
        p.writeln("Duration: %s" % self.duration)
      if self.goal_name is not None:
        p.writeln("Goal: " + self.goal_name)
      if self.deadline is not None:
        p.writeln("Deadline: " + self.deadline)
      for block in self.blocks:
        block.dump(p)

class Schedule:
  def __init__(self, blocks, loc):
    self.blocks = blocks
    self.loc = loc

  def dump(self, p):
    p.writeln("Schedule (%s)" % self.loc)
    with p:
      for block in self.blocks:
        block.dump(p)

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
    for day in range(ndays):
      d = iv.start + datetime.timedelta(days=day)
      if d.weekday() < 5 and not self.holidays.contains(d):
        effort -= 8
      if effort <= 0:
        return True, d
    return False, None

class GoalInfo:
  def __init__(self, name, completion_date):
    self.name = name
    self.completion_date = completion_date

  def dump(self, p):
    p.writeln("Goal '%s': %s" % (self.name, self.completion_date))

class ActivityInfo:
  def __init__(self, act, iv, alloc):
    self.act = act
    self.iv = iv
    self.alloc = alloc

  def dump(self, p):
    s = '/'.join([rc.name for rc in self.alloc])
    p.writeln("Activity %s: %s%s" % (self.act.name, self.iv,
                                     (" @%s" % s) if s else ""))

class AllocationInfo:
  def __init__(self, rc, holidays):
    self.rc = rc
    self.name = rc.name
    self.sheet = []
    self.cal = HolidayCalendar(holidays + rc.vacations)

  def allocate(self, start, effort):
    if not self.sheet:
      self.sheet = [I.Interval(start)]
      ret = self.allocate(start, effort)
      self.sheet = []
      return ret

    last_iv = I.Interval(datetime.date(datetime.MAXYEAR, 12, 31))
    for i, (left, right) in enumerate(zip(self.sheet, self.sheet[1:] + [last_iv])):
      gap = I.Interval(max(left.finish, start), right.start)
      ok, finish = self.cal.allows_effort(gap, effort)
      if not ok:
        continue
      iv = I.Interval(gap.start, finish)
      fragmentation = gap.start - left.finish
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
  def __init__(self, prj):
    self.goals = {}
    self.acts = {}
    self.rcs = {}
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

    # Find optimal resource count
    best_allocs = best_finish = None
    for i in range(1, n + 1):
      sched_data = []
      e = effort / i
      for rc in rcs:
        rc_info = self.rcs[rc.name]
        rc_effort = e * rc.efficiency
        j, iv, frag = rc_info.allocate(start, effort)
        sched_data.append((rc.name, j, iv, frag))
      sched_data.sort(key=lambda data: (data[2].finish, data[3]))  # I hate Python...
      finish = max(iv.finish for _1, _2, iv, _4 in sched_data[:i])
      if best_finish is None or finish < best_finish:
        best_allocs = sched_data[:i]
        best_finish = finish

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
    p.writeln("Timetable:")
    with p:
      for name, info in sorted(self.goals.items()):
        info.dump(p)
      for name, info in sorted(self.acts.items()):
        info.dump(p)
      for name, info in sorted(self.rcs.items()):
        info.dump(p)

class Scheduler:
  def __init__(self):
    self.prj = self.net = self.sched = self.table = None

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

  def _schedule_goal(self, goal, start, alloc):
    if goal.completion_date is not None:
      if goal.completion_date < start:
        warn(goal.loc, "goal '%s' is completed on %s, before %s"
                       % (goal.name, goal.completion_date, start))
      # TODO: warn if completion_date < start
      self.table.set_completion_date(goal, goal.completion_date)
      return goal.completion_date

    completion_date = start
    goal_alloc = set()
    for act in goal.preds:
      if act.duration is not None:
        # TODO: register spent time for devs
        if act.duration.start < start:
          warn(act.loc, "activity '%s' started on %s, before %s"
                        % (act.name, goal.completion_date, start))
        completion_date = max(completion_date, act.duration.finish)
        continue

      act_start = start
      if act.head is not None:
        if not self.table.is_completed(act.head):
          self._schedule_goal(act.head, datetime.date.today(), [])
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

      effort, _ = act.estimate()
      effort *= 1 - act.completion
      iv, assigned_rcs = self.table.assign_best_rcs(rcs, act_start, effort, act.parallel)
      self.table.set_duration(act, iv, assigned_rcs)
      completion_date = max(completion_date, iv.finish)

    self.table.set_completion_date(goal, completion_date)

    return completion_date

  def _schedule_block(self, block, start, alloc):
    alloc = block.alloc or alloc

    latest = start

    if block.goal_name is None:
      for b in block.blocks:
        last = self._schedule_block(b, start, alloc)
        latest = max(latest or last, last)
        if not block.par:
          start = last
    else:
      assert not block.blocks, "block with goals should have no subblocks"
      goal = self.net.name_to_goal.get(block.goal_name)
      error_if(goal is None, block.loc, "goal '%s' not found in plan" % block.goal_name)
      goal_finish = self._schedule_goal(goal, start, alloc)
      latest = max(latest, goal_finish)

    if block.deadline is not None and latest > block.deadline:
      print("Failed to schedule block at %s before deadline %s"
            % (block.loc, block.deadline))

    return latest

  def schedule(self, prj, net, sched):
    self.prj = prj
    self.net = net
    self.sched = sched
    self.table = Timetable(prj)
    start = datetime.date.today()
    for block in sched.blocks:
      self._schedule_block(block, start, [])
    return self.table
