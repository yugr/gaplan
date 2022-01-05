# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""APIs for simple user-controlled time-boxed scheduling."""

# This is WIP !!!

from gaplan.common.error import error, error_if, warn
import gaplan.common.matcher as M
import gaplan.common.parse as PA
import gaplan.common.interval as I

import datetime
import sys
import logging

logger = logging.getLogger(__name__)

class SchedBlock:
  """A unit of scheduling ("box") which contains a set of goals (or other blocks)
     and instructions on how to schedule them."""

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
        self.alloc, _ = PA.read_alloc(a, loc)
        continue

      if M.search(r'^[0-9]{4}-', a):
        self.duration = PA.read_date2(a, loc)
        continue

      if a.startswith('||'):
        self.parallel = PA.read_par(a)
        continue

      if not M.search(r'^([a-z_0-9]+)\s*(.*)', a):
        error(loc, f"failed to parse block attribute: {a}")
      k = M.group(1).strip()
      v = M.group(2).strip()

      if k == 'deadline':
        self.deadline, _ = PA.read_date(v, loc)
        continue

      error(loc, f"unknown block attribute '{k}'")

  def dump(self, p):
    block_type = "Sequential" if self.seq else "Parallel"
    p.writeln(f"{block_type} sched block ({self.loc})")
    with p:
      if self.duration is not None:
        p.writeln(f"Duration: {self.duration}")
      if self.goal_name is not None:
        p.writeln(f"Goal: {self.goal_name}")
        with p:
          if self.parallel is not None:
            p.writeln(f"parallelism: {self.parallel}")
          if self.alloc:
            p.writeln(f"alloc: {'/'.join(self.alloc)}")
      if self.deadline is not None:
        p.writeln(f"Deadline: {self.deadline}")
      for block in self.blocks:
        block.dump(p)

class SchedPlan:
  """Represents a hierarchy of blocks from declarative plan."""

  def __init__(self, blocks, loc):
    self.blocks = blocks
    self.loc = loc

  def dump(self, p):
    p.writeln(f"= SchedPlan at {self.loc} =\n")
    p.writeln("Blocks:")
    with p:
      for block in self.blocks:
        block.dump(p)
    p.writeln("")

class HolidayCalendar:
  """Holds info about holidays."""

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
  """Represents info about scheduled goal."""

  def __init__(self, name, completion_date):
    self.name = name
    self.completion_date = completion_date

  def dump(self, p):
    p.writeln(f"{self.name}: {self.completion_date}")

class ActivityInfo:
  """Represents info about scheduled activity."""

  def __init__(self, act, iv, alloc):
    self.act = act
    self.iv = iv
    self.alloc = alloc

  def dump(self, p):
    s = '/'.join([rc.name for rc in self.alloc])
    assignee = f" @{s}" if s else ""
    p.writeln(f"{self.act.name}: {self.iv}{assignee}")

class ResourceInfo:
  """Represents info about resource allocations."""

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

    logger.debug(f"allocate: allocating effort {effort} @{self.name} from {start}")

    last_iv = I.Interval(datetime.date(datetime.MAXYEAR, 12, 31))
    for i, (left, right) in enumerate(zip(self.sheet, self.sheet[1:] + [last_iv])):
      if start >= right.start:
        continue
      gap = I.Interval(max(left.finish, start), right.start)
      logger.debug(f"allocate: found free slot {gap}")
      ok, iv = self.cal.allows_effort(gap, effort)
      if not ok:
        logger.debug(f"allocate: slot {gap} rejected due to holidays")
        continue
      logger.debug(f"allocate: updated due to holidays: {iv}")
      fragmentation = iv.start - left.finish
      if gap.finish != sys.maxsize:
        fragmentation += gap.finish - iv.finish
      return i + 1, iv, fragmentation
    assert ""

  def dump(self, p):
    ss = []
    for iv in self.sheet:
      ss.append(f"{iv.start} - {iv.finish}")
    names = ', '.join(ss)
    p.writeln(f"{self.name}: {names}")

class Schedule:
  """Holds detailed scheduling info."""

  def __init__(self, prj):
    self.goals = {}
    self.acts = {}
    self.rcs = {}
    for rc in prj.members:
      self.rcs[rc.name] = ResourceInfo(rc, prj.holidays)

  def is_completed(self, goal):
    return goal.name in self.goals

  def get_completion_date(self, goal):
    return self.goals[goal.name].completion_date

  def set_completion_date(self, goal, d):
    error_if(self.is_completed(goal), 
             f"goal '{goal.name}' scheduled more than once")
    self.goals[goal.name] = GoalInfo(goal.name, d)

  def is_done(self, act):
    return act.name in self.acts

  def get_duration(self, act):
    return self.acts[act.name].iv

  def set_duration(self, act, iv, alloc):
    error_if(self.is_done(act), 
             f"activity '{act.name}' scheduled more than once")
    self.acts[act.name] = ActivityInfo(act, iv, alloc)

  def assign_best_rcs(self, rcs, start, effort, parallel):
    # How many chunks we can split work to?
    n = min(parallel, len(rcs))

    assignees = '/'.join(rc.name for rc in rcs)
    logger.debug(f"assign_best_rcs: allocate {effort}h @{assignees} ||{parallel}")

    # Find optimal resource count
    best_allocs = best_finish = None
    for i in range(1, n + 1):
      logger.debug(f"assign_best_rcs: use ||{i}")
      sched_data = []
      e = effort / i
      for rc in rcs:
        rc_info = self.rcs[rc.name]
        rc_effort = e / rc.efficiency
        j, iv, frag = rc_info.allocate(start, rc_effort)
        sched_data.append((rc.name, j, iv, frag))
      sched_data.sort(key=lambda data: (data[2].finish, data[3]))  # I hate Python...
      finish = max(iv.finish for _1, _2, iv, _4 in sched_data[:i])
      if best_finish is None or finish < best_finish:
        best_allocs = sched_data[:i]
        best_finish = finish
      assignees = '/'.join(name for name, _2, _3, _4 in sched_data[:i])
      logger.debug(f"assign_best_rcs: finishing on {iv.finish} @{assignees}")

    # We found optimal number of resources so perform allocation
    total_iv = None
    total_rcs = []
    for name, j, iv, _ in best_allocs:
      rc_info = self.rcs[name]
      rc_info.sheet.insert(j, iv)
      total_iv = iv if total_iv is None else total_iv.union(iv)
      total_rcs.append(rc_info.rc)

    return total_iv, total_rcs

  def dump(self, p):
    p.writeln("= Schedule =\n")

    p.writeln(f"Scheduled {len(self.goals)} goals and {len(self.acts)} activities\n")

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
    p.writeln("")

class Scheduler:
  """Schedule calculator."""

  def __init__(self, est):
    self.prj = self.net = self.sched_plan = self.sched = None
    self.est = est

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
      ts = self.sched.get_earliest_after(a.name, ts)
    t = W / sum(a.efficiency for a in alloc)
    return [(ts, t)] * len(alloc)

  def _schedule_goal(self, goal, start, alloc, par, warn_if_past=True):
    logger.debug(f"_schedule_goal: scheduling goal '{goal.name}': "
                 f"start={start}, alloc={alloc}, par={par}")

    if self.sched.is_completed(goal):
      return self.sched.get_completion_date(goal)

    if goal.completion_date is not None:
      logger.debug("_schedule_goal: goal already scheduled")
      if warn_if_past and goal.completion_date < start:
        warn(goal.loc, f"goal '{goal.name}' is completed on {goal.completion_date}, before {start}")
      # TODO: warn if completion_date < start
      self.sched.set_completion_date(goal, goal.completion_date)
      return goal.completion_date

    if goal.is_completed():
      warn(goal.loc, f"unable to schedule completed goal '{goal.name}' with no completion date")
      self.sched.set_completion_date(goal, datetime.date.today())
      return datetime.date.today()

    completion_date = start
    for act in goal.preds:
      logger.debug(f"_schedule_goal: scheduling activity '{act.name}' for goal '{goal.name}'")
      if act.duration is not None:
        # TODO: register spent time for devs
        if warn_if_past and act.duration.start < start:
          warn(act.loc, f"activity '{act.name}' started on {act.duration.start}, before {start}")
        completion_date = max(completion_date, act.duration.finish)
        continue

      act_start = start
      if act.head is not None:
        if self.sched.is_completed(act.head):
          act_start = max(act_start, self.sched.get_completion_date(act.head))
        else:
          # For goals that are not specified by schedule we use default settings
          logger.debug(f"_schedule_goal: scheduling predecessor '{act.head.name}'")
          self._schedule_goal(act.head, datetime.date.today(), [], None, warn_if_past=False)
          if not act.overlaps:
            act_start = max(act_start, self.sched.get_completion_date(act.head))
          else:
            for pred in self.head.preds:
              overlap = act.overlaps.get(pred.id)
              if overlap is not None:
                pred_iv = selt.sched.get_duration(pred)
                span = (pred_iv.finish - pred_iv.start) * (1 - overlap)
                act_start = max(act_start, pred_iv.start + span)

      if act.is_instant():
        completion_date = max(completion_date, act_start)
        continue

      plan_rcs = self.prj.get_resources(act.alloc)
      if alloc:
        rcs = self.prj.get_resources(alloc)
        if any(rc for rc in rcs if rc not in plan_rcs):
          allocs = '/'.join(alloc)
          assignees = '/'.join(rc.name for rc in plan_rcs)
          error(f"allocations defined in schedule ({allocs}) do not match "
                f"allocations defined in action ({assignees})")
      else:
        rcs = plan_rcs

      act_par = par
      if act_par is None:
        act_par = act.parallel

      act_effort, _ = self.est.estimate(act)
      act_effort *= 1 - act.effort.completion

      assignees = '/'.join(rc.name for rc in rcs)
      logger.debug(f"_schedule_goal: scheduling activity '{act.name}': "
                   f"start={act_start}, effort={act_effort}, par={act_par}, rcs={assignees}")

      iv, assigned_rcs = self.sched.assign_best_rcs(rcs, act_start, act_effort, act_par)
      assignees = '/'.join(rc.name for rc in assigned_rcs)
      logger.debug(f"_schedule_goal: assignment for activity '{act.name}': "
                   f"@{assignees}, duration {iv}")

      self.sched.set_duration(act, iv, assigned_rcs)
      completion_date = max(completion_date, iv.finish)

    logger.debug(f"_schedule_goal: scheduled goal '{goal.name}' for completion_date")
    self.sched.set_completion_date(goal, completion_date)

    if goal.deadline is not None and completion_date > goal.deadline:
      warn(f"failed to schedule goal '{goal.name}' before deadline goal.deadline")

    return completion_date

  def _schedule_block(self, block, start, alloc, par):
    logger.debug(f"_schedule_block: scheduling block in {block.loc}: "
                 f"start={start}, alloc={alloc}, par={par}")

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
      error_if(goal is None, block.loc, f"goal '{block.goal_name}' not found in plan")
      goal_finish = self._schedule_goal(goal, start, alloc, par)
      latest = max(latest, goal_finish)

    if block.deadline is not None and latest > block.deadline:
      warn("Failed to schedule block at {block.loc} before deadline {block.deadline}")

    return latest

  def schedule(self, prj, net, sched_plan):
    """Compute schedule based on scheduling plan."""
    self.prj = prj
    self.net = net
    self.sched_plan = sched_plan
    self.sched = Schedule(prj)
    for block in sched_plan.blocks:
      self._schedule_block(block, datetime.date.today(), [], None)
    return self.sched
