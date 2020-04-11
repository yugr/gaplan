# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
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

def add_common_attrs(loc, obj, attrs):
  """Adds attributes that are common for goals, checks and activities."""

  other_attrs = []
  for a in attrs:
    if re.match(r'JUST_AN_EXAMPLE', a):
      obj.tasks = set(a.split('/'))
      continue

    m = re.search(r'^([a-z]+)\s*(.*)', a)
    if m:
      k = m.group(1)
      v = m.group(2)
      if k == 'JUST_AN_EXAMPLE':
        obj.lag = PA.read_duration3(v, loc)
        continue

    other_attrs.append(a)

  return other_attrs

class Condition:
  """Class which describes single completion condition of a goal."""

  def __init__(self, name, status, loc):
    self.name = name
    self.loc = copy.copy(loc)

    # Other
    self.status = status

  def add_attrs(self, attrs, loc):
    attrs = add_common_attrs(loc, self, attrs)
    if attrs:
      error_loc(loc, "unknown condition attribute(s): %s" % ', '.join(attrs))

  def done(self):
    return self.status != ''

class Activity:
  """Class which describes an activity i.e. edge between two goals."""

  def __init__(self, loc):
    self.loc = copy.copy(loc)

    self.head = None
    self.tail = None
    self.globl = False  # Marks "global" activities which are enabled for all children of the target

    self.start_date = self.finish_date = None
    self.effort = ETA()
    self.alloc = []
    self.parallel = 0

    # TODO: also attach tasks to goals?
    self.jira_tasks = set()
    self.pull_requests = set()

    # TODO: add lags?

  def set_endpoints(self, g1, g2, is_pred):
    # Discriminate between "|<-" and "|->" edges
    if is_pred:
      self.head = g2
      self.tail = g1
    else:
      self.head = g1
      self.tail = g2

  def is_scheduled(self):
    return self.start_date is not None and self.finish_date is not None

  def is_max_parallel(self):
    return self.parallel == sys.maxsize

  def is_instant(self):
    return self.effort.real is None and self.effort.min is None

  def add_attrs(self, attrs, loc):
    attrs = add_common_attrs(loc, self, attrs)

    for a in attrs:
      if re.search(r'^[0-9]+(\.[0-9]+)?[hdwmy]', a):
        self.effort = PA.read_duration3(a, loc)
        continue

      if M.search(r'^@\s*(.*)', a):
        self.alloc = M.group(1).split('/')
        continue

      if M.search(r'^[0-9]{4}-', a):
        self.start_date, self.finish_date = PA.read_date2(a, loc)
        continue

      if M.match(r'^task\s+(.*)', a):
        self.jira_tasks.add(M.group(1))
        continue

      if M.match(r'^PR\s+(.*)', a):
        self.pull_requests.add(M.group(1))
        continue

      if M.match(r'^\|\|(\s*([0-9]+))?$', a):
        self.parallel = int(M.group(2)) if M.group(2) else sys.maxsize
        continue

      if not M.search(r'^([a-z_0-9]+)\s*(.*)', a):
        error_loc(loc, "failed to parse attribute: %s" % a)
      k = M.group(1)
#      v = M.group(2)
      if k == 'global':
        self.globl = True
      else:
        error_loc(loc, "unknown activity attribute: '%s'" % k)

  def check(self, warn):
    if warn == 0:
      return

    if self.alloc and not self.effort.defined():
      warn_loc(self.loc, 'activity is assigned but no effort is specified')

  def dump(self, p):
    p.writeln('%s -> %s' % (self.head.name if self.head else '',
                            self.tail.name if self.tail else ''))

    p.enter()

    p.writeln("Defined in %s" % self.loc)

    if self.jira_tasks:
      p.writeln('Tasks in tracker: %s' % ', '.join(self.jira_tasks))

    if self.pull_requests:
      p.writeln('Pull requests: %s' % ', '.join(self.pull_requests))

    avg, dev = self.effort.estimate(self.tail.risk if self.tail else None)
    if avg is not None:
      dev_str = (' +/- %dh' % (2 * dev)) if dev != 0 else ''
      p.writeln('estimated effort: %dh%s' % (avg, dev_str))

    if self.effort.real is not None:
      p.writeln('actual effort: %dh' % self.effort.real)

    if self.start_date is not None:
      p.writeln('fixed start date: %s' % PR.print_date(self.start_date))

    if self.finish_date is not None:
      p.writeln('fixed end date: %s' % PR.print_date(self.finish_date))

    if self.is_max_parallel():
      par = 'max'
    elif self.parallel:
      par = self.parallel
    else:
      par = 'non'
    par
    p.write('allocated: %s (%s-parallel)'
            % (', '.join(self.alloc) if self.alloc else 'any', par))

    p.exit()

class Goal:
  """Class which describes a single goal in plan."""

  def __init__(self, name, loc, dummy=False):
    self.name = name
    self.loc = copy.copy(loc)
    self.dummy = dummy
    self.alias = None

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
        if not Goal.MIN_PRIO <= self.prio <= Goal.MAX_PRIO:
          error_loc(loc, "invalid priority value %d" % self.prio)
        continue

      if a.find('?') == 0:
        self.risk = int(a[1:])
        if not Goal.MIN_RISK <= self.risk <= Goal.MAX_RISK:
          error_loc(loc, "invalid risk value %d" % self.risk)
        continue

      if M.search(r'^I[0-9]+$', a):
        self.iter = int(a[1:])
        continue

      if M.search(r'^[0-9]{4}-', a):
        self.completion_date, _ = PA.read_date(a, loc)
        continue

#      # Jira task format
#      if M.search(r'^[A-Z][A-Z_]*-[0-9]+$', a):
#        self.jira_tasks.append(a)
#        continue

      if not M.search(r'^([a-z_0-9]+)\s*(.*)', a):
        error_loc(loc, "failed to parse attribute: %s" % a)
      k = M.group(1)
      v = M.group(2)
      if k == 'deadline':
        self.deadline, _ = PA.read_date(v, loc)
      elif k == 'alias':
        self.alias, _ = PA.read_date(v, loc)
      else:
        error_loc(loc, "unknown goal attribute '%s'" % k)

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

  def check(self, warn):
    if warn and not self.defined and not self.dummy:
      warn_loc(self.loc, 'goal "%s" is undefined' % self.name)

    pending_conds = [c.name for c in self.checks if not c.done()]
    if warn and self.completion_date and pending_conds:
      warn_loc(self.loc, 'goal "%s" marked as completed but some checks are still pending:\n  %s' % (self.name, '\n  '.join(pending_conds)))

    for act in self.global_preds:
      if not act.is_instant():
        error_loc(act.loc, "global dependencies must be instant")

      if warn and not act.head:
        warn_loc(act.loc, "goal '%s' has empty global dependency" % self.name)

    for act in self.preds:
      act.check(warn)

      if act.head and self.iter is not None and act.head.iter is None:
        warn_loc(self.loc, "goal has been scheduled but one of it's dependents is not: '%s'" % act.head.name)

      if self.is_completed() and (not act.start_date or not act.effort.real):
        warn_loc(self.loc, "goal '%s' is achieved but one of it's actions is missing tracking data" % self.name)

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
        'alias',
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
      if isinstance(v, datetime.datetime):
        v = PR.print_date(v)
      if v is not None:
        p.writeln('%s: %s' % (name, v))

    if self.checks:
      p.writeln('%d check(s):' % len(self.checks))
      with p:
        for check in self.checks:
          p.writeln('[%s] %s' % (check.status, check.name))

    if self.preds:
      p.writeln('%d preceeding activity(s):' % len(self.preds))
      with p:
        for act in self.preds:
          act.dump(p)

    if self.global_preds:
      p.writeln('%d global preceeding activity(s):' % len(self.global_preds))
      with p:
        for act in self.global_preds:
          act.dump(p)

    if self.succs:
      p.writeln('%d succeeding activity(s):' % len(self.succs))
      with p:
        for act in self.succs:
          act.dump(p)

    if self.global_succs:
      p.writeln('%d global succeeding activity(s):' % len(self.global_succs))
      with p:
        for act in self.global_succs:
          act.dump(p)

    parents = self.parents()
    if parents:
      p.writeln('%d parent(s):' % len(self.parents()))
      with p:
        for g in parents:
          p.writeln('* %s' % g.name)

    if self.children:
      p.writeln('%d child(ren):' % len(self.children))
      with p:
        for i, g in enumerate(self.children):
          p.write('#%d:' % i)
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

  # TODO: change project to own net
  def __init__(self, project, roots, warn):
    self.project = project
    self.roots = roots
    self.name_to_goal = {}
    self.iter_to_goals = {}
    self._recompute(warn)

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
          warn_loc(g.loc, "inferred (%s) and assigned (%s) %s for goal '%s' do not match" % (new_attr, old_attr, attr_name, g.name))
          setattr(g, attr_name, new_attr)
    self.visit_goals(callback=assign_inferred_attrs)

  def _recompute(self, warn):
    """Computes aux data structures used for network analysis
       and propagates attributes."""

    # Index goals by name

    self.name_to_goal = {}
    def update_name_to_goal(g):
      self.name_to_goal[g.name] = g
      if g.alias is not None:
        other_goal = self.name_to_goal.get(g.alias, None)
        if other_goal is not None and other_goal.name != g.name:
          error("goals '%s' and '%s' use the same alias name '%s'"
                % (other_goal.name, g.name, g.alias))
        self.name_to_goal[g.alias] = g
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

  def filter(self, filtered_goals, warn):
    """Change network to include only supplied goals."""

    self.visit_goals(before=lambda g: g.filter(filtered_goals))

    new_roots = [g for g in self.roots if g.name in filtered_goals]
    if not new_roots:
      error("set of top goals is empty after filtering")

    self.roots = new_roots
    self._recompute(warn)

  def visit_goals(self, **args):
    visit_goals(self.roots, **args)

  def dump(self, p):
    self.project.dump(p)
    p.writeln('')
    for g in self.roots:
      g.dump(p)
      p.writeln('')

  def check(self, warn):
    if warn == 0:
      return

    # Some checks already performed before: iteration assignments do not violate deps, prios match

    self.visit_goals(callback=lambda g: g.check(warn))

    # Check that iterations are continuous and start from 0

    iters = set()
    def collect_iters(g):
      if g.iter is not None:
        iters.add(g.iter)
    self.visit_goals(callback=collect_iters)
    iters = sorted(list(iters))
    if warn and iters:
      if iters[0] != 1:
        warn("iterations do not start with 1")
      for itr, nxt in zip(iters, iters[1:]):
        if itr + 1 != nxt:
          warn("iterations are not consecutive: %d and %d" % (itr, nxt))
          break

    # Check for loops

    for root in self.roots:
      path = []
      def enter(g, path):
        if g.name in path:
          error("found a cycle:%s" % '\n  '.join(path))
        path.append(g.name)
      def exit(g, path):
        path = path[:-1]
      root.visit(before=lambda g: enter(g, path), after=lambda g: exit(g, path))
