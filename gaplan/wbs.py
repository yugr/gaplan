# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""APIs for converting declarative plan to WBS."""

import logging

from gaplan.common.error import error, warn, error_if, warn_if
import gaplan.common.interval as I

logger = logging.getLogger(__name__)

class Task:
  """Task is a named activity. Task can include other tasks."""

  def __init__(self, id, name, parent, act=None, goal=None):
    self.id = id
    self.name = name
    self.parent = parent
    self.activities = []
    self.milestones = []
    self.subtasks = []
    self.depends = set()
    if goal is not None:
      self._set_goal(goal)
    else:
      self.goal = self.prio = self.complete = None
      self.duration = self.deadline = None
    if act is not None:
      self.set_action(act)
    else:
      self.act = self.duration = None

  def check(self):
    """Verify invariants."""
    assert self.id is not None
    assert self.name is not None
    for t in self.activities:
      # Activities are effortful non-goal-based leaf tasks
      assert t.is_leaf()
      assert t.goal is None
      assert not t.subtasks
      assert not t.is_milestone()
      assert t.act
    for t in self.milestones:
      # Milestones are effortless non-goal-based leaf tasks
      assert t.is_leaf()
      assert t.goal is None
      assert not t.subtasks
      assert t.is_milestone()
      assert not t.act
      assert t.depends
    for t in self.subtasks:
      # Subtasks are goal-based tasks
      assert t.goal is not None

  def _set_goal(self, goal):
    self.goal = goal
    self.prio = goal.prio
    self.complete = goal.complete()
    if goal.completion_date is not None:
      self.duration = I.Interval(goal.completion_date)
    self.deadline = self.goal.deadline

  def set_action(self, act):
    self.act = act
    self.duration = act.duration

  def merge(self, task):
    for t in task.subtasks + task.milestones + task.activities:
      t.parent = self
    self.subtasks += task.subtasks
    self.milestones += task.milestones
    self.activities += task.activities

  def is_leaf(self):
    return not (self.activities or self.milestones or self.subtasks)

  def is_milestone(self):
    return self.id.endswith('_milestone')

  def pretty_name(self):
    if self.goal is None and self.parent is not None:
      return f"{self.parent.pretty_name()}: {self.name}"
    return self.name

  def update_activities(self):
    # TODO: what about milestones?
    for task in self.activities:
      for attr in ('prio',
                   'complete',
                   'duration'):
        setattr(task, attr, getattr(self, attr))

  def dump(self, p):
    p.writeln(f"Task {self.id} \"{self.pretty_name()}\"")
    with p:
      if self.goal:
        p.writeln(f"Goal \"{self.goal.name}\"")
      if self.act:
        self.act.dump(p)
      if self.activities:
        p.writeln("Activities")
        with p:
          for task in self.activities:
            task.dump(p)
      if self.milestones:
        p.writeln("Milestones")
        with p:
          for task in self.milestones:
            task.dump(p)
      if self.subtasks:
        p.writeln("Subtasks")
        with p:
          for task in self.subtasks:
            task.dump(p)

class WBS:
  """Represents Work Breakdown Structure generated from declarative plan."""

  def __init__(self, tasks):
    self.tasks = tasks

  def check(self):
    """Verify invariants."""
    self.visit_tasks(lambda t: t.check())

  def dump(self, p):
    p.writeln("WBS:")
    with p:
      for task in self.tasks:
        task.dump(p)

  def visit_tasks(self, cb):
    """Visitor pattern for task hierarchy."""
    def visit(task):
      cb(task)
      for t in task.activities:
        visit(t)
      for t in task.milestones:
        visit(t)
      for t in task.subtasks:
        visit(t)
    for task in self.tasks:
      visit(task)

def _is_goal_ignored(g):
  return g.dummy and not g.preds

# Do not print empty dummy activities
def _is_activity_ignored(act):
  return act.head is not None \
    and not act.effort.defined() \
    and _is_goal_ignored(act.head)

def _create_goal_task(goal, parent, ids):
  id = ids[goal.name]

  task = Task(id, goal.name, parent, goal=goal)

  for act in goal.global_preds:
    if act.head:
      task.depends.add(act.head.name)

  task_num = 1
  for a in goal.preds:
    if a.is_instant():
      task.depends.add(a.head.name)
    elif not _is_activity_ignored(a):
      # TODO: use a.id
      subtask = Task(f'{id}_{task_num}',
                     f"Implementation {task_num}", task, act=a)
      task.subtasks.append(subtask)
      task_num += 1

  return task

def _create_wbs_iterative(net, ids):
  user_iters = list(filter(lambda i: i is not None, net.iter_to_goals.keys()))
  error_if(not user_iters, "no iterations defined in plan")

  user_iters.sort()
  last_iter = (user_iters[-1] + 1) if user_iters else 0

  tasks = []

  for i in user_iters + [None]:
    i_num = last_iter if i is None else i

    task = Task(f'iter_{i_num}', f'Iteration {i_num}', None)
    task.depends.add(f'iter_{i_num - 1}')
    tasks.append(task)

    for g in net.iter_to_goals[i]:
      if not _is_goal_ignored(g):
        t = _create_goal_task(g, task, ids)
        task.subtasks.append(t)

  return WBS(tasks)

def _create_goal_task_hierarchical(goal, parent, ids, ancestors):
  id = ids[goal.name]
  task = Task(id, goal.name, parent, goal=goal)
  task.depends.update(a.head.name for a in goal.global_preds if a.head)

  # Creation of deps is a bit complicated here.
  # In general we can _not_ copy goal deps into parent task
  # because, due to semantics of WBS, this would mean that
  # all subtasks would inherit these dependencies.
  # 
  # We avoid this by creating artificial activities/milestones.

  task_num = ms_num = 1
  for a in goal.preds:
    if a.is_instant():
      t = Task(f'{id}_{ms_num}_milestone', f"External dep {ms_num} satisfied", task)
      t.depends.add(a.head.name)
      ms_num += 1
      task.milestones.append(t)
    else:
      t = Task(f"{id}_{task_num}", f"Implementation {task_num}", task, act=a)
      t.depends.add(a.head.name)
      task_num += 1
      task.activities.append(t)

  for g in goal.children:
    t = _create_goal_task_hierarchical(g, task, ids, ancestors)
    task.subtasks.append(t)

  return task

def _create_wbs_hierarchical(net, ids, ancestors):
  tasks = []
  for g in net.roots:
    task = _create_goal_task_hierarchical(g, None, ids, ancestors)
    tasks.append(task)
  return WBS(tasks)

def _optimize_task(task, ancestors):
  """Try to optimize structure of WBS
     by removing various dummy subtasks."""

  # Optimize kids

  for t in task.subtasks:
    _optimize_task(t, ancestors)

  logger.debug(f"_optimize_task: optimizing task {task.id} ({task.name})")

  # Eliminate useless intermediaries.

  old_subtasks = task.subtasks
  task.subtasks = []
  for t in old_subtasks:
    if t.goal and t.goal.dummy and not t.activities:
      logger.debug(f"_optimize_task: removing intermediate dummy task {t.id} ({t.name})")
      # All child activities are instant so we can remove it.
      # But be careful to update milestones and activities
      # which depended on it.
      task.depends.discard(t.name)
      for task_ in task.milestones + task.activities:
        if t.name in task_.depends:
          task_.depends.discard(t.name)
          for t_ in t.milestones:
            task_.depends.update(t_.depends)
          task_.depends.update(t_.name for t_ in t.subtasks)
      task.merge(t)
    else:
      task.subtasks.append(t)

  # Drop instant deps from ancestors.

  def is_ancestor(name):
    return name in ancestors[task.name]

  old_milestones = task.milestones
  task.milestones = []
  for t in old_milestones:
    external_deps = list(filter(lambda t: not is_ancestor(t), t.depends))
    if external_deps:
      task.milestones.append(t)
    else:
      logger.debug(f"_optimize_task: dropped instant dep {t.id} ({t.name})")

  # Merge all milestone subtasks into a one.

  if task.milestones:
    logger.debug(f"_optimize_task: merging all instant deps to {t.id} ({t.name})")
    id = task.id
    t = Task(id + '_milestone', "External deps satisfied", task)
    t.depends = {st for t in task.milestones for st in t.depends}
    task.milestones = [t]

  # Merge single dummy subtask into parent.

  if not task.subtasks:
    if not task.milestones and len(task.activities) == 1:
      t = task.activities[0]
      logger.debug(f"_optimize_task: merging activity {t.id} ({t.name})")
      assert not task.act
      task.set_action(t.act)
      task.depends.update(t.depends)
      task.activities = []

    if not task.activities and len(task.milestones) == 1:
      logger.debug(f"_optimize_task: merging milestone {t.id} ({t.name})")
      task.depends.update(task.milestones[0].depends)
      task.milestones = []

def create_wbs(net, hierarchy):
  """Generate WBS from declarative plan."""

  next_id = [0]  # Python's craziness
  ids = {}
  def assign_id(g):
    if g.name not in ids:
      if g.id is not None:
        ids[g.name] = g.id
      else:
        ids[g.name] = f'id_{next_id[0]}'
        next_id[0] += 1
  net.visit_goals(callback=assign_id)

  ancestors = {}
  def cache_ancestors(goal):
    ancestors[goal.name] = set()
    for g in goal.children:
      ancestors[g.name].add(g.name)
      ancestors[g.name].update(ancestors[g.name])
  net.visit_goals(after=cache_ancestors, hierarchical=True)

  if hierarchy:
    wbs = _create_wbs_hierarchical(net, ids, ancestors)
  else:
    wbs = _create_wbs_iterative(net, ids)

  wbs.check()

  for task in wbs.tasks:
    _optimize_task(task, ancestors)

  wbs.check()

  # Update activities from parent

  wbs.visit_tasks(lambda t: t.update_activities())

  # Change dependencies to task ids

  name2id = {}
  def index_ids(task):
    if task.goal is not None:
      name2id[task.goal.name] = task.id
  wbs.visit_tasks(index_ids)

  def update_depends(task):
    task.depends = [name2id[name] for name in list(task.depends)]
  wbs.visit_tasks(update_depends)

  return wbs
