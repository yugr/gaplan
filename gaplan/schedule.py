# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

from gaplan.common import matcher as M
from gaplan.common import printers as PR
from gaplan.common import parse as PA

class SchedBlock:
  def __init__(self, par, offset, loc):
    self.par = par
    self.offset = offset
    self.loc = loc
    self.alloc = []
    self.start_date = self.finish_date = None
    self.goals = []
    self.subblocks = []

  def add_goal(self, goal, goal_attrs):
    self.goals.append((goal, goal_attrs))  # TODO

  def add_attrs(self, attrs, loc):
    for a in attrs:
      if M.search(r'^@\s*(.*)', a):
        self.alloc = M.group(1).split('/')
        continue

      if M.search(r'^start\s+([0-9]{4}-.*)', a):
        self.start_date, _ = PA.read_date(M.group(1), loc)
        continue

      if M.search(r'^finish\s+([0-9]{4}-.*)', a):
        self.finisih_date, _ = PA.read_date(M.group(1), loc)
        continue

      error_loc(loc, "unknown activity attribute: '%s'" % k)

  def dump(self, p):
    p.writeln("%s sched block (%s)" % ("Parallel" if self.par else "Sequential", self.loc))
    with p:
      if self.start_date is not None:
        p.writeln("Start: %s" % PR.print_date(self.start_date))
      if self.finish_date is not None:
        p.writeln("Finish: %s" % PR.print_date(self.finish_date))
      for goal_name, goal_attrs in self.goals:
        p.writeln(goal_name)
      for block in self.subblocks:
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

class Scheduler:
  def __init__(self):
    pass

  def schedule(self, net, sched):
    return Timetable()

class Timetable:
  def __init__(self):
    pass

  def dump(self, p):
    p.writeln("TODO")
