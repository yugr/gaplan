# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import re

from gaplan.common import parse as PA

class SchedBlock:
  def __init__(self, par, offset, loc):
    self.par = par
    self.offset = offset
    self.loc = loc
    self.goals = []
    self.subblocks = []

  def add_goal(self, goal, goal_attrs):
    self.goals.append((goal, goal_attrs))  # TODO

  def add_attrs(self, attrs, loc):
    pass  # TODO

  def dump(self, p):
    p.writeln("%s sched block (%s)" % ("Parallel" if self.par else "Sequential", self.loc))
    with p:
      for goal, goal_attrs in self.goals:
        p.writeln(goal.name)
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
