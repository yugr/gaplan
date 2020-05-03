# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# This module provides APIs for parsing declarative plans.

import re

from gaplan.common.error import error, error_if
from gaplan.common import parse as PA
from gaplan.common import matcher as M
from gaplan.common.location import Location
from gaplan import project
from gaplan import schedule
from gaplan import goal as G

class LexemeType:
  LARROW     = "|<-"
  RARROW     = "|->"
  CHECK      = "|[]"
  GOAL       = "GOAL"
  ATTR_START = "//"
  LIST_ELT   = "LIST_ELT"
  PRJ_ATTR   = "PRJ_ATTR"
  ASSIGN     = "="
  SCHED      = 'SCHED'
  COMMA      = ','
  EOF        = ''

class LexerMode:
  NORMAL = "NORMAL"
  ATTR   = "ATTR"

class Lexer(PA.BaseLexer):
  def __init__(self, v=0):
    super(Lexer, self).__init__(v)
    self.mode = LexerMode.NORMAL

  def reset(self, filename, f):
    super(Lexer, self).reset(filename, f)
    self.mode = LexerMode.NORMAL

  def update_on_newline(self):
    self.mode = LexerMode.NORMAL
    # Strip comments
    self.line = re.sub(r'#.*$', '', self.line)
    # And trailing whites
    self.line = self.line.rstrip()

  def next_internal(self):
    if self.line == '':
      # File exhausted
      type = LexemeType.EOF
      data = text = ''
    elif self.mode == LexerMode.ATTR:
      nest = 0
      self.line = self.line.lstrip()
      if self.line[0] == ',':
        type = ','
        i = 1
      else:
        type = LexemeType.LIST_ELT
        for i, c in enumerate(self.line):
          if c == ',' and not nest:
            break
          elif c == '(':
            nest += 1
          elif c == ')':
            nest -= 1
        else:
          i += 1
          self.mode = LexerMode.NORMAL
      text = self.line[:i]
      data = text.rstrip()
      self.line = self.line[i:]
    else:
      data = None
      if M.match(r'( *)\|([<>])-', self.line):
        type = LexemeType.LARROW if M.group(2) == '<' else LexemeType.RARROW
        data = len(M.group(1))
      elif M.match(r'( *)\|\[([^\]]*)\]\s*(.*?)(?=(//|$))', self.line):
        type = LexemeType.CHECK
        data = len(M.group(1)), M.group(2), M.group(3).strip()
      elif M.match(r'^(\s*)(--|\|\|)\s*', self.line):
        type = LexemeType.SCHED
        data = len(M.group(1)), M.group(2)
      elif M.match(r'( *)\|(.*?)(?=//|$)', self.line):
        type = LexemeType.GOAL
        data = len(M.group(1)), M.group(2).strip()
      elif M.match(r'\s*//', self.line):
        type = LexemeType.ATTR_START
        self.mode = LexerMode.ATTR
      elif M.match(r'([A-Za-z][A-Za-z0-9_]*)(?=\s*=)', self.line):
        type = LexemeType.PRJ_ATTR
        data = M.group(1)
      elif M.match(r'\s*=\s*', self.line):
        type = LexemeType.ASSIGN
        self.mode = LexerMode.ATTR
      else:
        error(self._loc(), "unexpected syntax: %s" % self.line)
      self.line = self.line[len(M.group(0)):]
      text = M.group(0)
    self.lexemes.append(PA.Lexeme(type, data, text, self._loc()))

class Parser(PA.BaseParser):
  def __init__(self, v=0):
    super(Parser, self).__init__(Lexer(v), v)
    self.dummy_goal_count = self.project_attrs = self.names = None

  def reset(self, filename, f):
    super(Parser, self).reset(filename, f)
    self.dummy_goal_count = 0
    self.project_attrs = {}
    self.names = {}

  def parse_attrs(self):
    a = []
    while True:
      l = self.lex.next_if(LexemeType.LIST_ELT)
      if l is None:
        break
      self._dbg("parse_attrs: new attribute: %s" % l)
      a.append(l.data)
      if not self.lex.next_if(','):
        break
    return a

  def maybe_parse_goal_decl(self, offset):
    l = self.lex.peek()
    if l.type != LexemeType.GOAL:
      return None, []

    self._dbg("maybe_parse_goal_decl: goal: %s" % l)
    goal_offset, goal_name = l.data
    if offset != goal_offset:
      self._dbg("maybe_parse_goal_decl: not a subgoal, exiting")
      return None, []
    self.lex.skip()

    a = []
    l = self.lex.next_if(LexemeType.ATTR_START)
    if l is not None:
      while True:
        l = self.lex.next_if(LexemeType.LIST_ELT)
        if l is None:
          break
        a.append(l.data)
        self._dbg("maybe_parse_goal_decl: new attribute: %s" % l)
        l = self.lex.next_if(',')
        if l is None:
          break
    return goal_name, a

  def parse_edge(self):
    l = self.lex.expect([LexemeType.LARROW, LexemeType.RARROW])
    act = G.Activity(l.loc)
    self._dbg("parse_edge: new activity: l")

    if self.lex.next_if(LexemeType.ATTR_START) is not None:
      a = self.parse_attrs()
      act.add_attrs(a, act.loc)

    return act

  def parse_checks(self, g, goal_offset):
    while True:
      l = self.lex.next_if(LexemeType.CHECK)
      if l is None:
        return
      self._dbg("parse_checks: new check: %s" % l)

      check_offset, status, text = l.data
      error_if(check_offset != goal_offset, l.loc, "check is not properly nested")
      error_if(status not in ['X', 'F', ''], l.loc, "unexpected check status: '%s'" % status)

      check = G.Condition(text, status, l.loc)
      g.add_check(check)

      if self.lex.next_if(LexemeType.ATTR_START) is not None:
        a = self.parse_attrs()
        check.add_attrs(a, l.loc)

  def parse_subgoals(self, goal, offset):
    while True:
      l = self.lex.peek()
      if l.type not in [LexemeType.LARROW, LexemeType.RARROW]:
        return
      self._dbg("parse_subgoals: new edge: %s" % l)

      is_pred = l.type == LexemeType.LARROW
      edge_offset = l.data
      if edge_offset != offset:
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
    goal_name, goal_attrs = self.maybe_parse_goal_decl(offset)

    if goal_name is None:
      if not allow_empty:
        return None
      # The infamous PERT dummy goals
      goal = self._make_dummy_goal(loc)
      was_defined = False
      self._dbg("parse_goal: creating dummy goal")
    else:
      goal = self.names.get(goal_name)
      if goal is None:
        was_defined = False
        goal = self.names[goal_name] = G.Goal(goal_name, loc)
        self._dbg("parse_goal: parsed new goal: %s" % goal.name)
      else:
        was_defined = goal.defined
        self._dbg("parse_goal: parsed existing goal: %s" % goal.name)

    if goal_attrs:
      error_if(was_defined, loc, "duplicate definition of goal '%s' (previous definition was in %s)" % (goal.name, goal.loc))
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

    self.lex.expect('=')

    rhs = []
    while True:
      l = self.lex.expect('LIST_ELT')
      rhs.append(l.data)
      if not self.lex.next_if(','):
        break

    def expect_one_value(loc, name, vals):
      error_if(len(vals) != 1, loc, "too many values for attribute '%s': %s" % (name, ', '.join(vals)))

    if name in ['name', 'tracker_link', 'pr_link']:
      expect_one_value(l.loc, name, rhs)
      val = rhs[0]
    elif name in ['start', 'finish']:
      expect_one_value(l.loc, name, rhs)
      val, _ = PA.read_date(rhs[0], attr_loc)
    elif name == 'members':
      val = []
      for rc_info in rhs:
        if not M.match(r'([A-Za-z][A-Za-z0-9_]*)\s*(?:\(([^\)]*)\))?', rc_info):
          error(attr_loc, "failed to parse resource declaration: %s" % rc_info)
        rc_name, attrs = M.groups()
        rc = project.Resource(rc_name, attr_loc)
        if attrs:
          rc.add_attrs(re.split(r'\s*,\s*', attrs), attr_loc)
        val.append(rc)
    elif name == 'teams':
      val = []
      for team_info in rhs:
        if not M.match(r'\s*([A-Za-z][A-Za-z0-9_]*)\s*\(([^)]*)\)$', team_info):
          error(attr_loc, "invalid team declaration: %s" % team_info)
        team_name = M.group(1)
        rc_names = re.split(r'\s*,\s*', M.group(2).strip())
        val.append(project.Team(team_name, rc_names, attr_loc))
    elif name == 'holidays':
      val = []
      for s in rhs:
        iv = PA.read_date2(s, attr_loc)
        val.append(iv)
    else:
      error(attr_loc, "unknown project attribute: %s" % name)

    self.project_attrs[name] = val

  def parse_sched_block(self, offset):
    l = self.lex.peek()
    top_loc = l.loc

    if l.data[0] != offset:
      return None
    self.lex.skip()

    block = schedule.SchedBlock(l.data[1] == '--', l.data[0], top_loc)

    # Parse attributes

    if self.lex.next_if(LexemeType.ATTR_START):
      attrs = []
      while True:
        l = self.lex.expect(LexemeType.LIST_ELT)
        attrs.append(l.data)
        if not self.lex.next_if(','):
          break
      block.add_attrs(attrs, top_loc)

    # Parse goals and subblocks in this block

    while True:
      l = self.lex.peek()
      if l.type == LexemeType.GOAL:
        goal_name, goal_attrs = self.maybe_parse_goal_decl(offset + 2)
        if goal_name is None:
          break
        block.add_goal(goal_name, goal_attrs, l.loc)
      elif l.type == LexemeType.SCHED:
        self._dbg("parse_sched_block: new block: %s" % l)
        subblock = self.parse_sched_block(offset + 2)
        if subblock is None:
          break
        self._dbg("parse_sched_block: new subblock: %s" % l)
        block.blocks.append(subblock)
      else:
        break

    return block

  def parse(self, W):
    net_loc = project_loc = sched_loc = Location()

    root_goals = []
    root_blocks = []
    while True:
      l = self.lex.peek()
      if l is None:
        break
      self._dbg("parse: next lexeme: %s" % l)
      if l.type == LexemeType.GOAL:
        error_if(l.data[0] != 0, l.loc, "root goal '%s' must be left-adjusted" % l.data[1])
        goal = self.parse_goal(l.data[0], None, False)
        if not net_loc:
          net_loc = goal.loc
        root_goals.append(goal)
      elif l.type == LexemeType.PRJ_ATTR:
        if not project_loc:
          project_loc = l.loc
        self.parse_project_attr()
      elif l.type == LexemeType.SCHED:
        error_if(l.data[0] != 0, l.loc, "root block must be left-adjusted")
        block = self.parse_sched_block(l.data[0])
        if not sched_loc:
          sched_loc = block.loc
        root_blocks.append(block)
      elif l.type == LexemeType.EOF:
        break
      else:
        # TODO: anonymous goals
        error(l.loc, "unexpected lexeme: '%s'" % l.text)

    net = G.Net(root_goals, W, net_loc)

    prj = project.Project(project_loc)
    prj.add_attrs(self.project_attrs)

    sched = schedule.Schedule(root_blocks, sched_loc)

    return net, prj, sched
