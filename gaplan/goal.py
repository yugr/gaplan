# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# This file provides APIs for representing core project maps concepts:
# goals and arrows.

import sys
import re
import datetime
import operator
import copy

from gaplan.common.error import error, warn, error_if, warn_if
from gaplan.common.ETA import ETA
from gaplan.common import parse as PA
from gaplan.common import matcher as M

def add_common_attrs(loc, obj, attrs):
  """Adds attributes that are common for goals, checks and activities."""

  other_attrs = []
  for a in attrs:
    if M.search(r'^([A-Za-z][A-Za-z0-9_]*)\s*(.*)', a):
      k = M.group(1).strip()
      v = M.group(2).strip()
      if k == 'task':
        obj.tracker.tasks = set(M.group(1).split('/'))
        continue
      elif k == 'PR':
        obj.tracker.prs = set(M.group(1).split('/'))
        continue

    other_attrs.append(a)

  return other_attrs

class TrackerLink:
  """Contains info about tasks and PRs in external tracker."""

  def __init__(self):
    self.tasks = set()
    self.prs = set()

  def dump(self, p):
    if self.tasks:
      p.writeln('Tasks: %s' % ', '.join(self.tasks))

    if self.prs:
      p.writeln('PRs: %s' % ', '.join(self.prs))

class Condition:
  """Class which describes single completion condition of a goal."""

  def __init__(self, name, status, loc):
    self.name = name
    self.loc = copy.copy(loc)

    # Other
    self.status = status
    self.tracker = TrackerLink()

  def add_attrs(self, attrs, loc):
    attrs = add_common_attrs(loc, self, attrs)
    error_if(attrs, loc, "unknown condition attribute(s): %s" % ', '.join(attrs))

  def done(self):
    return self.status != ''

class Activity:
  """Class which describes an activity i.e. edge between two goals."""

  def __init__(self, loc):
    self.loc = copy.copy(loc)

    # Deps
    self.id = None
    self.head = None
    self.tail = None
    self.globl = False  # Marks "global" activities which are enabled for all children of the target

    # Timing
    self.duration = None
    self.effort = ETA()
    self.alloc = ['all']
    self.real_alloc = []
    self.parallel = 1
    self.overlaps = {}
    self.completion = 0

    # Other
    self.tracker = TrackerLink()

  def set_endpoints(self, g1, g2, is_pred):
    # Discriminate between "|<-" and "|->" edges
    if is_pred:
      self.head = g2
      self.tail = g1
    else:
      self.head = g1
      self.tail = g2

  def is_scheduled(self):
    return self.duration is not None

  def is_max_parallel(self):
    return self.parallel == sys.maxsize

  def is_instant(self):
    return self.effort.real is None and self.effort.min is None

  def add_attrs(self, attrs, loc):
    attrs = add_common_attrs(loc, self, attrs)

    for a in attrs:
      if re.search(r'^[0-9]+(\.[0-9]+)?[hdwmy]', a):
        self.effort = PA.read_effort3(a, loc)
        continue

      if a.startswith('@'):
        self.alloc, self.real_alloc = PA.read_alloc(a)
        continue

      # TODO: specify in effort attribute?
      if M.search(r'^[0-9]{4}-', a):
        self.duration = PA.read_date2(a, loc)
        continue

      if M.search(r'^([0-9]+)%', a):
        self.completion = float(M.group(1)) / 100
        continue

      if M.match(r'^id\s+(.*)', a):
        self.id = M.group(1)

      if M.match(r'over\s+(\S+)\s+(.*)', a):
        other_id = M.group(1)
        overlap, a = PA.read_float(M.group(2))
        if a == '%':
          overlap /= 100
        self.overlaps[other_id] = overlap

      if a.startswith('||'):
        self.parallel = PA.read_par(a)
        continue

      if not M.search(r'^([a-z_0-9]+)\s*(.*)', a):
        error(loc, "failed to parse attribute: %s" % a)
      k = M.group(1).strip()
      v = M.group(2).strip()

      if k == 'global':
        self.globl = True
        continue

      error(loc, "unknown activity attribute: '%s'" % k)

  def check(self, W):
    if W == 0:
      return

    if self.alloc and not self.effort.defined():
      warn(self.loc, "activity is assigned but no effort is specified")

  def estimate(self):
    return self.effort.estimate(self.tail.risk if self.tail else None)

  @property
  def name(self):
    return "%s -> %s%s" % (self.head.pretty_name if self.head else '',
                           self.tail.pretty_name if self.tail else '',
                           (" (%s)" if self.id else ""))

  def dump(self, p):
    p.writeln(self.name)

    p.enter()

    p.writeln("Defined in %s" % self.loc)

    self.tracker.dump(p)

    avg, dev = self.estimate()
    if avg is not None:
      dev_str = (' +/- %dh' % (2 * dev)) if dev != 0 else ''
      p.writeln("estimated effort: %dh%s" % (avg, dev_str))

    if self.effort.real is not None:
      p.writeln("actual effort: %dh" % self.effort.real)

    if self.duration is not None:
      p.writeln("duration: %s" % self.duration)

    p.writeln("completion: %d%%" % int(100 * self.completion))

    if self.is_max_parallel():
      par = 'max'
    elif self.parallel > 1:
      par = self.parallel
    else:
      par = 'non'
    p.writeln("allocated: %s (%s-parallel)%s"
            % (', '.join(self.alloc) if self.alloc else 'any', par,
               ("(actual %s)" % ', '.join(self.real_alloc)) if self.real_alloc else ""))
    if self.overlaps:
      p.write("overlaps: ")
      p.writeln(', '.join('%s (%g)' % (id, over) for id, over in sorted(self.overlaps.items())))

    p.exit()

class Goal:
  """Class which describes a single goal in plan."""

  def __init__(self, name, loc, dummy=False):
    self.name = name
    self.loc = copy.copy(loc)
    self.dummy = dummy
    self.id = None

    # Completion criteria
    self.checks = []

    # Deps
    self.preds = []
    self.global_preds = []
    self.succs = []
    self.global_succs = []

    # WBS info
    self.parent = None
    self.children = []
    self.depth = 0

    # Timings
    self.deadline = None
    self.completion_date = None
    self.iter = None

    # Other
    self.defined = False
    self.risk = None
    self.prio = None
    self.tracker = TrackerLink()

  def add_activity(self, act, is_pred):
    # TODO: check if activity is already present to avoid dups
    lst = None
    if is_pred and act not in self.preds:
      lst = self.global_preds if act.globl else self.preds
    elif not is_pred and act not in self.succs:
      lst = self.global_succs if act.globl else self.succs
    if lst is not None:
      lst.append(act)

  def is_scheduled(self):
    return self.completion_date is not None

  def add_child(self, goal):
    self.children.append(goal)
    goal.parent = self

  def add_check(self, check):
    self.checks.append(check)

  MIN_PRIO = 1
  MAX_PRIO = 3

  MIN_RISK = 1
  MAX_RISK = 3

  def add_attrs(self, attrs, loc):
    attrs = add_common_attrs(loc, self, attrs)

    for a in attrs:
      if a.find('!') == 0:
        self.prio = int(a[1:])
        error_if(not Goal.MIN_PRIO <= self.prio <= Goal.MAX_PRIO,
                 loc, "invalid priority value %d" % self.prio)
        continue

      if a.find('?') == 0:
        self.risk = int(a[1:])
        error_if(not Goal.MIN_RISK <= self.risk <= Goal.MAX_RISK,
                 loc, "invalid risk value %d" % self.risk)
        continue

      if M.search(r'^I[0-9]+$', a):
        self.iter = int(a[1:])
        continue

      if M.search(r'^[0-9]{4}-', a):
        self.completion_date, _ = PA.read_date(a, loc)
        continue

      if not M.search(r'^([a-z_0-9]+)\s*(.*)', a):
        error(loc, "failed to parse goal attribute: %s" % a)
      k = M.group(1).strip()
      v = M.group(2).strip()

      if k == 'deadline':
        self.deadline, _ = PA.read_date(v, loc)
        continue

      if k == 'id':
        self.id = v
        continue

      error(loc, "unknown goal attribute '%s'" % k)

  @property
  def pretty_name(self):
    if not self.dummy:
      return self.name
    names = []
    for pred in self.preds:
      if pred.head:
        names.append(pred.head.pretty_name)
    return ', '.join(names)

  def parents(self):
    ps = []
    p = self.parent
    while p is not None:
      ps.append(p)
      p = p.parent
    ps.reverse()
    return ps

  def priority(self):
    """Combined priority which uses both risk and assigned priority."""
    prio = None if self.prio is None else float(self.prio) / Goal.MAX_PRIO
    risk = None if self.risk is None else float(self.risk) / Goal.MAX_RISK
    if prio is not None and risk is not None:
      # TODO: do something more reasonable
      alpha = 2.0 / 3
      return prio * alpha + risk * (1 - alpha)
    elif prio is not None:
      return prio
    elif risk is not None:
      return risk
    else:
      return None

  def complete(self):
    if self.completion_date is not None:
      return 100

    # If goal underspecified, return 0 to be conservative
    if not self.checks:
      return 0

    res = total = 0
    for c in self.checks:
      total += 1
      if c.done():
        res += 100
    return int(round(float(res) / total))

  def is_completed(self):
    return self.complete() == 100

  # Such goals may be identified with their underlying activities
  # (which is useful for export to scheduling tools).
  def has_single_activity(self):
    return len(self.preds) == 1

  def is_instant(self):
    """Is this a milestone i.e. all preceding edges are instant?"""
    for act in self.preds:
      if not act.is_instant():
        return False
    return True

  def visit(self, visited=None, **args):
    """Visitor pattern of goal network.
       Supports both hierarchical and dependency-based traversals."""

    if visited is None:
      visited = set()

    if self.name in visited:
      return

    visited.add(self.name)

    before = args.get('before', args.get('callback', None))
    after = args.get('after', None)

    if before is not None:
      before(self)

    if args.get('hierarchical', False):
      for g in self.children:
        g.visit(visited, **args)
    else:
      if args.get('preds', True):
        for act in self.preds:
          if act.head:
            act.head.visit(visited, **args)

      if args.get('succs', True):
        for act in self.succs:
          if act.tail:
            act.tail.visit(visited, **args)

    if after is not None:
      after(self)

  def check(self, W):
    if W and not self.defined and not self.dummy:
      warn(self.loc, "goal '%s' is undefined" % self.name)

    pending_conds = [c.name for c in self.checks if not c.done()]
    if W and self.completion_date is not None \
        and self.completion_date <= datetime.date.today() \
        and pending_conds:
      warn(self.loc, "goal '%s' marked as completed but some checks are still pending:\n  %s" % (self.name, '\n  '.join(pending_conds)))

    if W and self.is_completed() and not self.completion_date:
      warn(self.loc, "goal '%s' marked as completed but is missing tracking data"
                     % self.name)

    for act in self.global_preds:
      if not act.is_instant():
        error(act.loc, "global dependencies must be instant")

      if W and not act.head:
        warn(act.loc, "goal '%s' has empty global dependency" % self.name)

    for act in self.preds:
      act.check(W)

      if act.head and self.iter is not None and act.head.iter is None:
        warn(self.loc, "goal has been scheduled but one of it's dependents is not: '%s'" % act.head.name)

      if self.is_completed() and (not act.duration or not act.effort.real):
        warn(self.loc, "goal '%s' is achieved but one of it's actions is missing tracking data" % self.name)

  def filter(self, only_goals):
    new_preds = []
    for act in self.preds:
      if act.head is not None and act.head.name in only_goals:
        new_preds.append(act)
    self.preds = new_preds

    new_global_preds = []
    for act in self.global_preds:
      if act.head is not None and act.head.name in only_goals:
        new_global_preds.append(act)
    self.global_preds = new_global_preds

    new_succs = []
    for act in self.succs:
      if act.head is not None and act.head.name in only_goals:
        new_succs.append(act)
    self.succs = new_succs

    new_global_succs = []
    for act in self.global_succs:
      if act.head is not None and act.head.name in only_goals:
        new_global_succs.append(act)
    self.global_succs = new_global_succs

    new_children = []
    for g in self.children:
      if g.name in only_goals:
        new_children.append(act)
    self.children = new_children

  def dump(self, p):
    p.writeln(self.name + (' (dummy)' if self.dummy else ''))

    p.enter()

    for attr in [
        'loc',
        'id',
        'depth',
        'prio',
        'risk',
        ('iteration', 'iter'),
        'deadline',
        ('completed', 'completion_date')]:
      if isinstance(attr, tuple):
        (name, attr) = attr
      else:
        name = attr
      v = getattr(self, attr)
      if v is not None:
        p.writeln("%s: %s" % (name, v))

    self.tracker.dump(p)

    if self.checks:
      p.writeln("%d check(s):" % len(self.checks))
      with p:
        for check in self.checks:
          p.writeln("[%s] %s" % (check.status, check.name))

    if self.preds:
      p.writeln("%d preceeding activity(s):" % len(self.preds))
      with p:
        for act in self.preds:
          act.dump(p)

    if self.global_preds:
      p.writeln("%d global preceeding activity(s):" % len(self.global_preds))
      with p:
        for act in self.global_preds:
          act.dump(p)

    if self.succs:
      p.writeln("%d succeeding activity(s):" % len(self.succs))
      with p:
        for act in self.succs:
          act.dump(p)

    if self.global_succs:
      p.writeln("%d global succeeding activity(s):" % len(self.global_succs))
      with p:
        for act in self.global_succs:
          act.dump(p)

    parents = self.parents()
    if parents:
      p.writeln("%d parent(s):" % len(self.parents()))
      with p:
        for g in parents:
          p.writeln('* %s' % g.name)

    if self.children:
      p.writeln("%d child(ren):" % len(self.children))
      with p:
        for i, g in enumerate(self.children):
          p.write("#%d:" % i)
          with p:
            g.dump(p)

    p.exit()

def visit_goals(goals, visited=None, **args):
  if visited is None:
    visited = set()
  for g in goals:
    g.visit(visited, **args)

class Net:

  """Class which represents a single declarative plan (goals, iterations, etc.)."""

  def __init__(self, roots, W, loc):
    self.roots = roots
    self.loc = loc
    self.name_to_goal = {}
    self.iter_to_goals = {}
    self._recompute(W)

  def _propagate_attr(self, attr_name, join, less):
    """Performs backward propagation of attribute from goals for which it's defined."""

    wl = set()
    inferred_attrs = {}
    def init_wl(g):
      if getattr(g, attr_name) is not None:
        inferred_attrs[g.name] = getattr(g, attr_name)
        for act in g.preds:
          if act.head:
            wl.add(act.head)
    self.visit_goals(callback=init_wl)

    while wl:
      g = wl.pop()

      succ_attrs = []
      if g.name in inferred_attrs:
        succ_attrs.append(inferred_attrs[g.name])
      for act in g.succs:
        if act.tail and act.tail.name in inferred_attrs:
          succ_attrs.append(inferred_attrs[act.tail.name])

      new_attr = join(succ_attrs)
      if g.name not in inferred_attrs or new_attr != inferred_attrs[g.name]:
        inferred_attrs[g.name] = new_attr
        for act in g.preds:
          if act.head:
            wl.add(act.head)

    def assign_inferred_attrs(g):
      new_attr = inferred_attrs.get(g.name)
      if new_attr is not None:
        old_attr = getattr(g, attr_name)
        if old_attr is None:
          setattr(g, attr_name, new_attr)
        elif less(old_attr, new_attr):
          warn(g.loc, "inferred (%s) and assigned (%s) %s for goal '%s' do not match" % (new_attr, old_attr, attr_name, g.name))
          setattr(g, attr_name, new_attr)
    self.visit_goals(callback=assign_inferred_attrs)

  def _recompute(self, W):
    """Computes aux data structures used for network analysis
       and propagates attributes."""

    # Index goals by name

    self.name_to_goal = {}
    def update_name_to_goal(g):
      self.name_to_goal[g.name] = g
      if g.id is not None:
        other_goal = self.name_to_goal.get(g.id, None)
        error_if(other_goal is not None and other_goal.name != g.name,
                 "goals '%s' and '%s' use the same id '%s'"
                 % (other_goal.name, g.name, g.id))
        self.name_to_goal[g.id] = g
    self.visit_goals(callback=update_name_to_goal)

    # Assign parents for goals which are not explicitly nested

    for g in self.name_to_goal.values():
      if g.parent is None and g not in self.roots:
        if g.succs:
          # First successor becomes parent
          g.succs[0].tail.add_child(g)
        else:
          self.roots.append(g)

    # Compute depths

    depth = [0]
    def enter(g):
      g.depth = depth[0]
      depth[0] += 1
    def exit(g):
      depth[0] -= 1
    self.visit_goals(before=enter, after=exit, hierarchical=True)

    # Propagate assigned priorities and iterations

    self._propagate_attr('prio', max, operator.lt)
    self._propagate_attr('iter', min, operator.ge)

    # Index iterations

    self.iter_to_goals = {}
    def update_iter_to_goals(g):
      self.iter_to_goals.setdefault(g.iter, []).append(g)
    self.visit_goals(callback=update_iter_to_goals)

  def filter(self, filtered_goals, W):
    """Change network to include only supplied goals."""

    self.visit_goals(before=lambda g: g.filter(filtered_goals))

    new_roots = [g for g in self.roots if g.name in filtered_goals]
    error_if(not new_roots, "set of top goals is empty after filtering")

    self.roots = new_roots
    self._recompute(W)

  def visit_goals(self, **args):
    visit_goals(self.roots, **args)

  def dump(self, p):
    p.writeln("= Network at %s =\n" % self.loc)

    num_actions = [0]
    def update_num_actions(g):
      num_actions[0] += len(g.preds)
    self.visit_goals(callback=update_num_actions)
    # TODO: more stats
    p.writeln("Network contains %d goals (%d roots) and %d actions\n"
              % (len(self.name_to_goal), len(self.roots), num_actions[0])) 

    for g in self.roots:
      g.dump(p)
      p.writeln('')

  def check(self, W):
    if W == 0:
      return

    # Some checks already performed before: iteration assignments do not violate deps, prios match

    self.visit_goals(callback=lambda g: g.check(W))

    # Check that iterations are continuous and start from 0

    iters = set()
    def collect_iters(g):
      if g.iter is not None:
        iters.add(g.iter)
    self.visit_goals(callback=collect_iters)
    iters = sorted(list(iters))
    if W and iters:
      warn_if(iters[0] != 1, "iterations do not start with 1")
      for itr, nxt in zip(iters, iters[1:]):
        if itr + 1 != nxt:
          warn("iterations are not consecutive: %d and %d" % (itr, nxt))
          break

    # Check for loops

    for root in self.roots:
      path = []
      def enter(g, path):
        error_if(g.name in path, "found a cycle:%s" % '\n  '.join(path))
        path.append(g.name)
      def exit(g, path):
        path[:] = path[:-1]
      root.visit(before=lambda g: enter(g, path), after=lambda g: exit(g, path))
