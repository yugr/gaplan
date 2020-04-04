# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import re
import datetime

from gaplan.common.error import error, error_loc
from gaplan.common import parse as P
from . import project
from . import goal as G

def parse_attrs(s, loc):
  ss = s.split('//')
  if len(ss) == 1:
    return [], s
  if len(ss) > 2:
    error_loc(loc, 'unexpected duplicate attributes: %s' % s)
  s = ss[0].rstrip()
  a = re.split(r'\s*[,;]\s*', ss[1].strip())
  return a, s

def is_goal_decl(s):
  return re.match(r'^ *\|[^\[<>]', s)

def parse_goal_decl(s, offset, loc, names):
  a, s = parse_attrs(s, loc)
  m = re.search(r'^( *)\|([^\[<>].*)$', s)
  if not m:
    return None, []
  name = m.group(2)
  goal_offset = len(m.group(1))
  if goal_offset != offset:
    return None, []
  if name in names:
    goal = names[name]
  else:
    goal = G.Goal(name, loc)
    names[name] = goal
  return goal, a

def is_edge(s):
  return re.search(r'^ *\|(<-|->)', s)

def is_incoming_edge(s):
  return s.find('<') != -1

def parse_edge(s, loc):
  act = G.Activity(loc)

  attrs, s = parse_attrs(s, loc)
  act.add_attrs(attrs, loc)

  m = re.search(r'^( *)\|[<>-][<>-]', s)
  if not m:
    error_loc(loc, 'failed to parse edge: %s' % s)

  return act, len(m.group(1))

def is_check(s):
  return re.match(r'^ *\|\[', s)

def parse_check(s, loc):
  a, s = parse_attrs(s, loc)
  m = re.search(r'^( *)\|\[([^\]]*)\] *(.+)$', s)
  if not m:
    error_loc(loc, 'failed to parse check: %s' % s)
  status = m.group(2)
  if status not in ['X', 'F', '']:
    error_loc(loc, 'unexpected status: "%s"' % status)
  check = G.Condition(m.group(3), status, loc)
  check.add_attrs(a, loc)
  return check, len(m.group(1))

def parse_checks(f, g, offset):
  while True:
    s, loc = f.peek()
    if s is None or not is_check(s):
      return
    f.skip()
    check, check_offset = parse_check(s, loc)
    if offset != check_offset:
      error_loc(loc, 'check is not properly nested')
    g.add_check(check)

def parse_subgoals(f, goal, offset, names):
  while True:
    s, loc = f.peek()
    if s is None or not is_edge(s):
      return

    is_pred = is_incoming_edge(s)
    act, edge_offset = parse_edge(s, loc)
    if edge_offset < offset:
      return

    f.skip()

    subgoal = parse_goal(f, edge_offset + len('|<-'), names, goal,
                         allow_empty=True)
    act.set_endpoints(goal, subgoal, is_pred)
    goal.add_activity(act, is_pred)
    if subgoal:
      subgoal.add_activity(act, not is_pred)

dummy_goal_count = 0

def _make_dummy_goal(loc, names):
  count = getattr(_make_dummy_goal, 'count', 0)
  setattr(_make_dummy_goal, 'count', count + 1)
  name = 'dummy_%d' % count
  goal = G.Goal(name, loc, dummy=True)
  names[name] = goal
  return goal

def parse_goal(f, offset, names, parent, allow_empty=False):
  s, loc = f.peek()

  goal = None
  if s is not None:
    goal, goal_attrs = parse_goal_decl(s, offset, loc, names)
    if goal:
      f.skip()

  if goal is None:
    if not allow_empty:
      return None
    goal = _make_dummy_goal(loc, names)

  was_defined = goal.defined
  if goal_attrs:
    if was_defined:
      error_loc(loc, 'duplicate definition of goal "%s" (previous definition was in %s)' % (goal.name, goal.loc))
    goal.add_attrs(goal_attrs, loc)

  # TODO: Gaperton's examples contain interwined checks and deps
  parse_checks(f, goal, offset)

  parse_subgoals(f, goal, offset, names)

  if not was_defined and (goal.checks or goal_attrs):
    goal.defined = True
    if parent is not None:
      parent.add_child(goal)

  return goal

def is_project_attribute(s):
  return re.match(r'^\s*\w+\s*=', s)

def parse_project_attribute(s, loc):
  m = re.search(r'^\s*(\w+)\s*=\s*(.*)', s)
  if m is None:
    error_loc(loc, 'unexpected line: %s' % s)

  name = m.group(1)
  val = m.group(2)

  if name in ['name', 'tracker_link', 'pr_link']:
    return name, val

  if name in ['start', 'finish']:
      val, _ = P.read_date(val, loc)
      return name, val

  if name == 'members':
    members = []
    for member in map(lambda m: m.strip(), val.split(',')):
      m = re.search(r'^([A-Za-z_0-9]+)\s*(?:\((.*)\))?$', member)
      if m is None:
        error_loc(loc, 'failed to parse member declaration: %s' % member)
      eff = float(m.group(2)) if m.group(2) else 1.0
      members.append(G.Member(m.group(1), eff))
    return name, members

  error_loc(loc, 'unknown project attribute: %s' % name)

def parse_goals(filename, f):
  f = P.Lexer(filename, f)
  prj = project.ProjectInfo()

  goals = []
  names = {}
  prj_attrs = {}

  while True:
    s, loc = f.peek()
    if s is None:
      break
    # TODO: anonymoddus goals
    elif is_goal_decl(s):
      goal = parse_goal(f, 0, names, None)
      goals.append(goal)
    elif is_project_attribute(s):
      k, v = parse_project_attribute(s, loc)
      f.skip()
      prj_attrs[k] = v
    else:
      error_loc(loc, 'unexpected line: "%s"' % s)

  prj.add_attrs(prj_attrs)

  return prj, goals
