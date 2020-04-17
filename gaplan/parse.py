# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import re

from gaplan.common.error import error_loc
from gaplan.common import parse as PA
from gaplan.common import matcher as M
from gaplan import project
from gaplan import schedule
from gaplan import goal as G

class Lexeme:
  LARROW     = "|<-"
  RARROW     = "|->"
  CHECK      = "|[]"
  GOAL       = "GOAL"
  ATTR_START = "//"
  LIST_ELT   = "LIST_ELT"
  PRJ_ATTR   = "PRJ_ATTR"
  ASSIGN     = "="
  COMMA      = ','
  EOF        = ''

  def __init__(self, type, data, text, loc):
    self.type = type
    self.data = data
    self.loc = loc
    self.text = text

  def __str__(self):
    return '%s: %s: %s' % (self.loc, self.type, self.data)

class Lexer(PA.BaseLexer):
  def __init__(self, v=0):
    super(Lexer, self).__init__(v)
    self.attr_mode = None

  def reset(self, filename, f):
    super(Lexer, self).reset(filename, f)
    self.attr_mode = False

  def update_on_newline(self):
    self.attr_mode = False
    # Strip comments
    self.line = re.sub(r'#.*$', '', self.line)
    # And trailing whites
    self.line = self.line.rstrip()

  def next_internal(self):
    if self.line == '':
      # File exhausted
      type = Lexeme.EOF
      data = text = ''
    elif self.attr_mode:
      nest = 0
      self.line = self.line.lstrip()
      if self.line[0] == ',':
        type = ','
        i = 1
      else:
        type = Lexeme.LIST_ELT
        for i, c in enumerate(self.line):
          if c == ',' and not nest:
            break
          elif c == '(':
            nest += 1
          elif c == ')':
            nest -= 1
        else:
          i += 1
          self.attr_mode = False
      text = self.line[:i]
      data = text.rstrip()
      self.line = self.line[i:]
    else:
      data = None
      if M.match(r'( *)\|([<>])-', self.line):
        type = Lexeme.LARROW if M.group(2) == '<' else Lexeme.RARROW
        data = len(M.group(1))
      elif M.match(r'( *)\|\[([^\]]*)\]\s*(.*?)(?=(//|$))', self.line):
        type = Lexeme.CHECK
        data = len(M.group(1)), M.group(2), M.group(3).strip()
      elif M.match(r'( *)\|(.*?)(?=//|$)', self.line):
        type = Lexeme.GOAL
        data = len(M.group(1)), M.group(2).strip()
      elif M.match(r'\s*//', self.line):
        type = Lexeme.ATTR_START
        self.attr_mode = True
      elif M.match(r'([A-Za-z][A-Za-z0-9_]*)(?=\s*=)', self.line):
        type = Lexeme.PRJ_ATTR
        data = M.group(1)
      elif M.match(r'\s*=\s*', self.line):
        type = Lexeme.ASSIGN
        self.attr_mode = True
      else:
        error_loc(self._loc(), "unexpected syntax: %s" % self.line)
      self.line = self.line[len(M.group(0)):]
      text = M.group(0)
    self.lexemes.append(Lexeme(type, data, text, self._loc()))

class Parser(PA.BaseParser):
  def __init__(self, v=0):
    super(Parser, self).__init__(Lexer(v), v)
    self.dummy_goal_count = self.project_attrs = self.names = self.project_loc = None

  def reset(self, filename, f):
    super(Parser, self).reset(filename, f)
    self.dummy_goal_count = 0
    self.project_attrs = {}
    self.project_loc = None
    self.names = {}

  def parse_attrs(self):
    a = []
    while True:
      l = self.lex.next_if(Lexeme.LIST_ELT)
      if l is None:
        break
      self._dbg("parse_attrs: new attribute: %s" % l)
      a.append(l.data)
      if not self.lex.next_if(','):
        break
    return a

  def maybe_parse_goal_decl(self, offset):
    l = self.lex.peek()
    if l.type != Lexeme.GOAL:
      return None, []

    self._dbg("maybe_parse_goal_decl: goal: %s" % l)
    goal_offset, goal_name = l.data
    if offset != goal_offset:
      self._dbg("maybe_parse_goal_decl: not a subgoal, exiting")
      return None, []
    self.lex.skip()

    goal = self.names.get(goal_name)
    if goal is None:
      goal = self.names[goal_name] = G.Goal(goal_name, l.loc)

    a = []
    l = self.lex.next_if(Lexeme.ATTR_START)
    if l is not None:
      while True:
        l = self.lex.next_if(Lexeme.LIST_ELT)
        if l is None:
          break
        a.append(l.data)
        self._dbg("maybe_parse_goal_decl: new attribute: %s" % l)
        l = self.lex.next_if(',')
        if l is None:
          break
    return goal, a

  def parse_edge(self):
    l = self.lex.expect([Lexeme.LARROW, Lexeme.RARROW])
    act = G.Activity(l.loc)
    self._dbg("parse_edge: new activity: l")

    if self.lex.next_if(Lexeme.ATTR_START) is not None:
      a = self.parse_attrs()
      act.add_attrs(a, act.loc)

    return act

  def parse_checks(self, g, goal_offset):
    while True:
      l = self.lex.next_if(Lexeme.CHECK)
      if l is None:
        return
      self._dbg("parse_checks: new check: %s" % l)

      check_offset, status, text = l.data
      if check_offset != goal_offset:
        error_loc(loc, "check is not properly nested")
      if status not in ['X', 'F', '']:
        error_loc(loc, "unexpected check status: '%s'" % status)

      check = G.Condition(text, status, l.loc)
      g.add_check(check)

      if self.lex.next_if(Lexeme.ATTR_START) is not None:
        a = parse_attrs()
        check.add_attrs(a, loc)

  def parse_subgoals(self, goal, offset):
    while True:
      l = self.lex.peek()
      if l.type not in [Lexeme.LARROW, Lexeme.RARROW]:
        return
      self._dbg("parse_subgoals: new edge: %s" % l)

      is_pred = l.type == Lexeme.LARROW
      edge_offset = l.data
      if edge_offset < offset:
        return
      self._dbg("parse_subgoals: new subgoal: %s" % l)

      act = self.parse_edge()
      subgoal = self.parse_goal(edge_offset + len('|<-'),
                                goal, is_pred, allow_empty=True)
      act.set_endpoints(goal, subgoal, is_pred)

      goal.add_activity(act, is_pred)
      if subgoal:
        subgoal.add_activity(act, not is_pred)

  def _make_dummy_goal(self, loc):
    name = 'dummy_%d' % self.dummy_goal_count
    self.dummy_goal_count += 1
    goal = G.Goal(name, loc, dummy=True)
    self.names[name] = goal
    return goal

  def parse_goal(self, offset, other_goal, is_pred, allow_empty=False):
    self._dbg("parse_goal: start lex: %s" % self.lex.peek())
    loc = self.lex.loc()
    goal, goal_attrs = self.maybe_parse_goal_decl(offset)

    if goal is None:
      if not allow_empty:
        return None
      goal = self._make_dummy_goal(loc)
      self._dbg("parse_goal: creating dummy goal")
    self._dbg("parse_goal: parsed goal: %s" % goal.name)

    was_defined = goal.defined
    if goal_attrs:
      if was_defined:
        error_loc(loc, 'duplicate definition of goal "%s" (previous definition was in %s)' % (goal.name, goal.loc))
      goal.add_attrs(goal_attrs, loc)

    # TODO: Gaperton's examples contain interwined checks and deps
    self.parse_checks(goal, offset)

    self.parse_subgoals(goal, offset)

    if not was_defined and (goal.checks or goal_attrs or goal.children):
      goal.defined = True
      if other_goal is not None and is_pred:
        other_goal.add_child(goal)

    return goal

  def parse_project_attr(self):
    l = self.lex.next()
    name = l.data
    attr_loc = l.loc
    if self.project_loc is None:
      self.project_loc = attr_loc

    self.lex.expect('=')

    rhs = []
    while True:
      l = self.lex.expect('LIST_ELT')
      rhs.append(l.data)
      if not self.lex.next_if(','):
        break

    def expect_one_value(name, vals):
      if len(vals) != 1:
        error_loc(loc, "too many values for attribute '%s': %s" % (name, ', '.join(vals)))

    if name in ['name', 'tracker_link', 'pr_link']:
      expect_one_value(name, rhs)
      val = rhs[0]
    elif name in ['start', 'finish']:
      expect_one_value(name, rhs)
      val, _ = PA.read_date(rhs[0], attr_loc)
    elif name == 'members':
      val = []
      for rc_info in rhs:
        if not M.match(r'([A-Za-z][A-Za-z0-9_]*)\s*(?:\(([^\)]*)\))?', rc_info):
          error_loc(attr_loc, "failed to parse resource declaration: %s" % rc_info)
        rc_name, attrs = M.groups()
        rc = project.Resource(rc_name, attr_loc)
        if attrs:
          rc.add_attrs(re.split(r'\s*,\s*', attrs), attr_loc)
        val.append(rc)
    elif name == 'teams':
      val = []
      for team_info in rhs:
        if not M.match(r'\s*([A-Za-z][A-Za-z0-9_]*)\s*\(([^)]*)\)$', team_info):
          error_loc(attr_loc, "invalid team declaration: %s" % team_info)
        team_name = M.group(1)
        rc_names = re.split(r'\s*,\s*', M.group(2).strip())
        val.append(project.Team(team_name, rc_names, attr_loc))
    else:
      error_loc(attr_loc, 'unknown project attribute: %s' % name)

    self.project_attrs[name] = val

  def parse(self):
    roots = []
    while True:
      l = self.lex.peek()
      if l is None:
        break
      self._dbg("parse: next lexeme: %s" % l)
      if l.type == Lexeme.GOAL and l.data[0] == 0:
        goal = self.parse_goal(0, None, False)
        roots.append(goal)
      elif l.type == Lexeme.PRJ_ATTR:
        self.parse_project_attr()
      elif l.type == Lexeme.EOF:
        break
      else:
        # TODO: anonymous goals
        error_loc(l.loc, "unexpected lexeme: '%s'" % l.text)

    prj = project.Project(self.project_loc)
    prj.add_attrs(self.project_attrs)

    sched = schedule.Schedule()

    return prj, roots, sched
