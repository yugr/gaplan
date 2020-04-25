# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# This module contains APIs for simple user-controlled scheduling.

# This is WIP !!!

from gaplan.common.error import error, error_if
from gaplan.common import matcher as M
from gaplan.common import printers as PR
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

      error(loc, "unknown block attribute: '%s'" % a)

  def dump(self, p):
    p.writeln("%s sched block (%s)" % ("Parallel" if self.par else "Sequential", self.loc))
    with p:
      if self.duration is not None:
        p.writeln("Start: %s" % PR.print_date(self.duration.start))
        p.writeln("Finish: %s" % PR.print_date(self.duration.finish))
      if self.goal_name:
        p.writeln("Goal: " + self.goal_name)
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

class GoalInfo:
  def __init__(self, name, iv, alloc):
    self.name = name
    self.iv = iv
    self.alloc = alloc

  def dump(self, p):
    s = '/'.join([rc.name for rc in self.alloc])
    p.writeln("Goal '%s': %s%s" % (self.name, self.iv,
                                           (" @%s" % s) if s else ""))

class AllocationInfo:
  def __init__(self, rc):
    self.rc = rc
    self.name = rc.name
    self.sheet = []

  def allocate(self, iv):
    if not self.sheet:
      return 0, iv, datetime.timedelta(0)
    last_iv = I.Interval(datetime.datetime(datetime.MAXYEAR, 12, 31))
    for i, (left, right) in enumerate(zip(self.sheet, self.sheet[1:] + [last_iv])):
      gap = I.Interval(left.finish, right.start)
      if (gap.start >= iv.start and gap.length >= iv.length) \
          or (gap.start < iv.start and gap.length >= iv.length + (iv.start - gap.start)):
        new_start = max(iv.start, gap.start)
        iv = I.Interval(new_start, new_start + iv.length)
        fragmentation = new_start - gap.start
        if gap.finish != sys.maxsize:
          fragmentation += gap.finish - iv.finish
        return i + 1, iv, fragmentation
    assert ""

  def dump(self, p):
    ss = []
    for iv in self.sheet:
      ss.append("%s - %s" % (PR.print_date(iv.start), PR.print_date(iv.finish)))
    p.writeln("%s: %s" % (self.name, ', '.join(ss)))

class Timetable:
  def __init__(self, prj):
    self.goal_infos = {}
    self.rc_infos = {}
    for rc in prj.members:
      self.rc_infos[rc.name] = AllocationInfo(rc)

  def set_goal_scheduled(self, goal, iv, alloc):
    self.goal_infos[goal.name] = GoalInfo(goal.name, iv, alloc)

  def is_goal_scheduled(self, goal):
    return goal.name in self.goal_infos

  def get_goal_finish(self, goal):
    return self.goal_infos[goal.name].iv.finish

  def assign_best_rcs(self, rcs, start, effort, parallel):
    # TODO: # select best resource from list
    # (or N resources if parallel) and compute optimal time
    best_rc = best_frag = best_iv = None
    for rc in rcs:
      rc_info = self.rc_infos[rc.name]
      rc_effort = effort * rc.efficiency
      iv = I.Interval(start, start + datetime.timedelta(hours=rc_effort))
      _, iv, frag = rc_info.allocate(iv)
      if best_frag is None \
          or iv.finish < best_iv.finish \
          or iv.finish == best_iv.finish and frag < best_frag:
        best_rc = rc
        best_frag = frag
        best_iv = iv
    rc_info = self.rc_infos[best_rc.name]
    i, best_iv, _ = rc_info.allocate(best_iv)
    rc_info.sheet.insert(i, best_iv)
    return best_iv, [best_rc]

  def dump(self, p):
    p.writeln("Timetable:")
    with p:
      for name, info in sorted(self.goal_infos.items()):
        info.dump(p)
      for name, info in sorted(self.rc_infos.items()):
        info.dump(p)

def nonones(*args):
  return filter(lambda x: x is not None, args)

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
      # TODO: register spent time for devs
      # TODO: warn if completion_date < start
      self.table.set_goal_scheduled(goal.name, I.Interval(goal.completion_date), [])
      return goal.completion_date

    goal_iv = I.Interval(start, start)
    goal_alloc = set()
    for act in goal.preds:
      if act.duration is not None:
        # TODO: register spent time for devs
        # TODO: warn if goal_start < start
        goal_iv = goal_iv.union(act.duration)
        continue

      act_start = start
      if act.head is not None:
        if not self.table.is_goal_scheduled(act.head):
          self._schedule_goal(act.head, datetime.datetime.now(), [])
        act_start = max(act_start, self.table.get_goal_finish(act.head))

      if act.is_instant():
        goal_iv = goal_iv.union(I.Interval(act_start, act_start))
        continue

      plan_rcs = self.prj.get_resources(act.alloc)
      if alloc:
        block_rcs = self.prj.get_resources(alloc)
        if block_rcs.difference(plan_rcs):
          error("allocations defined in schedule (%s) do not match "
                "allocations defined in action (%s)"
                % ('/'.join(alloc), '/'.join(rc.name for rc in plan_rcs)))
      else:
        rcs = plan_rcs

      effort, _ = act.estimate()
      iv, assigned_rcs = self.table.assign_best_rcs(rcs, act_start, effort, act.parallel)
      goal_alloc.update(assigned_rcs)
      goal_iv = goal_iv.union(iv)

    self.table.set_goal_scheduled(goal, goal_iv, goal_alloc)

    return goal_iv.finish

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

    return latest

  def schedule(self, prj, net, sched):
    self.prj = prj
    self.net = net
    self.sched = sched
    self.table = Timetable(prj)
    start = datetime.datetime.now()
    for block in sched.blocks:
      self._schedule_block(block, start, [])
    return self.table
