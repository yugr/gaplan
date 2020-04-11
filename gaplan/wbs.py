# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import sys
import re
import datetime
import operator
import copy

from gaplan.common.error import error, error_loc, warn_loc
from gaplan.common.ETA import ETA
from gaplan.common import parse as PA
from gaplan.common import printers as PR
from gaplan.common import matcher as M

class Task:
  """Task is basically a named activity."""

  def __init__(self, id, name, act):
    self.id = id
    self.name = name
    self.act = act
    self.goal = None
    self.subtasks = []
    self.depends = []

  def dump(self, p):
    p.writeln("Task %s \"%s\"" % (self.id, self.name))
    with p:
      if self.goal:
        p.writeln("Goal \"%s\"" % self.goal.name)
      if self.act:
        self.act.dump(p)
      for task in self.subtasks:
        task.dump(p)

class WBS:
  def __init__(self, tasks):
    self.tasks = tasks

  def dump(self, p):
    p.writeln("WBS:")
    with p:
      for task in self.tasks:
        task.dump(p)

def _is_goal_ignored(g):
  return g.dummy and not g.preds

# Do not print empty dummy activities
def _is_activity_ignored(act):
  return act.head is not None \
    and not act.effort.defined() \
    and _is_goal_ignored(act.head)

def _create_goal_task(goal, ids):
  id = ids[goal.name]

  task = Task(id, goal.name, None)
  task.goal = goal

  for act in goal.global_preds:
    if act.head:
      task.depends.append(act.head.name)

  if goal.has_single_activity():
    # Translate atomic goals to atomic TJ tasks
    task.act = goal.preds[0]
  else:
    task_num = 1
    for a in goal.preds:
      if a.is_instant():
        task.depends.append(a.head.name)
      elif not _is_activity_ignored(a):
        task.subtasks.append(Task(id + '_%d' % task_num,
                                  "Implementation %d" % task_num, a))
        task_num += 1

  return task

def _create_wbs_iterative(net, ids):
  user_iters = list(filter(lambda i: i is not None, net.iter_to_goals.keys()))
  user_iters.sort()
  last_iter = (user_iters[-1] + 1) if user_iters else 0

  tasks = []

  for i in user_iters + [None]:
    i_num = last_iter if i is None else i

    task = Task('iter_%d' % i_num, 'Iteration %d' % i_num, None)
    task.depends.append('iter_%d' % (i_num - 1))
    tasks.append(task)

    for g in net.iter_to_goals[i]:
      if not _is_goal_ignored(g):
        t = _create_goal_task(g, ids)
        task.subtasks.append(t)

  return WBS(tasks)

def _create_goal_task_hierarchical(goal, ids, ancestors):
  id = ids[goal.name]
  task = Task(id, goal.name, None)
  task.goal = goal
  task.depends += [a.head.name for a in goal.global_preds if a.head]

  # TODO: avoid dummy tasks if possible?

  # Creation of deps is a bit complicated here.
  # In general we can _not_ copy goal deps into parent task
  # because, due to semantics of WBS, this would mean that
  # all child tasks would inherit these dependencies.
  # 
  # We have to avoid this by creating artificial subtasks.
  # 
  # But there are special cases when we can do better:
  # * if dependencies are from ancestors and are instant,
  #   we can simply drop them (due to hierarchical nature of WBS)
  # * if there are no children and only single non-instant dependency,
  #   we can merge activity into the current task
  # * if there are no children and only instant dependencies,
  #   task is a milestone and we can simply copy deps to the task

  def is_ancestor(g):
    return g is None or g.name in ancestors[goal.name]

  # Ignore instant deps from ancestors
  preds = [a for a in goal.preds
           if not (a.is_instant() and is_ancestor(a.head))]

  # Ignore fake kids
  children = [g for g in goal.children if not (g.dummy and not g.preds)]

  if not preds:
    # No dependencies
    pass
  elif not children and goal.has_single_activity():
    # No dependencies
    # Merge dependency directly into task
    if len(preds) == 1:
      task.act = preds[0]
  elif not children and all(a.is_instant() for a in preds):
    # Direct dependencies at task
    task.depends += [a.head.name for a in preds]
  else:
    # Generic case: add dummy subtasks
    task_num = 1
    milestone_task = None
    for a in preds:
      if not is_ancestor(a.head) and a.is_instant():
        # Create single sub-milestone for all instant dependencies
        if not milestone_task:
          milestone_task = Task(id + '_milestone', "External deps satisfied", None)
        milestone_task.depends.append(a.head.name)
      elif not a.is_instant():
        task.subtasks.append(Task("%s_%d" % (id, task_num),
                                  "Implementation %d" % task_num, a))
        task_num += 1
    if milestone_task:
      task.subtasks.append(milestone_task)

  for goal in children:
    t = _create_goal_task_hierarchical(goal, ids, ancestors)
    task.subtasks.append(t)

  return task

def _create_wbs_hierarchical(net, ids):
  ancestors = {}
  def cache_ancestors(g):
    ancestors[g.name] = set()
    for child in g.children:
      ancestors[g.name].add(child.name)
      ancestors[g.name].update(ancestors[child.name])
  net.visit_goals(after=cache_ancestors, hierarchical=True)

  tasks = []
  for g in net.roots:
    task = _create_goal_task_hierarchical(g, ids, ancestors)
    tasks.append(task)

  return WBS(tasks)

def create_wbs(net, hierarchy):
  next_id = [0]  # Python's craziness
  ids = {}
  def assign_id(g):
    if g.name not in ids:
      if g.alias is not None:
        ids[g.name] = g.alias
      else:
        ids[g.name] = 'id_%d' % next_id[0]
        next_id[0] += 1
  net.visit_goals(callback=assign_id)

  if hierarchy:
    wbs = _create_wbs_hierarchical(net, ids)
  else:
    wbs = _create_wbs_iterative(net, ids)

  return wbs
