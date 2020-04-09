# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import re
import datetime

from gaplan.common.error import error, error_loc
from gaplan.common import parse as P
from gaplan.common import matcher as M

class Resource:
  """Describes a single developer."""

  def __init__(self, name):
    self.name = name
    self.efficiency = 1.0
    self.vacations = []

  def add_attrs(self, attrs, loc):
    for a in attrs:
      if M.search(r'^[0-9.]+$', a):
        self.efficiency = float(a)
      elif M.search(r'vacation\s+(.*)', a):
        start, finish = P.read_date2(M.group(1), loc)
        self.vacations.append((start, finish))
      else:
        error_loc("unexpected resource attribute: %s" % a)

  def dump(self, p):
    p.writeln('Developer %s (%f)' % (self.name, self.efficiency))
    time_format = '%Y-%m-%d'
    vv = []
    for start, finish in self.vacations:
      vv.append('%s - %s' % (start.strftime(time_format), finish.strftime(time_format)))
    p.writeln('  vacations: %s' % ', '.join(vv))

class Team:
  """Describes a team of developers."""

  def __init__(self, name, members):
    self.name = name
    self.members = members

  def dump(self, p):
    p.writeln("Team %s:")
    p.enter()
    for rc in self.members:
      rc.dump(p)
    p.exit()

class ProjectInfo:
  """Describes project resources."""

  def __init__(self):
    self.name = 'Unknown'
    year = datetime.datetime.today().year
    self.start = datetime.date(year, 1, 1)
    self.finish = datetime.date(year, 12, 31)
    self.members = []
    self.members_map = {}
    self.teams = {}
    self.teams_map = {}
    self.tracker_link = 'http://jira.localhost/browse/%s'
    self.pr_link = None

  def _recompute(self):
    self.members_map = {m.name : m for m in self.members}
    self.teams_map = {t.name : t for t in self.teams}
    if 'all' in self.teams_map:
      error_loc(self.teams_map['all'].loc, "predefined goal 'all' overriden")
    self.teams_map['all'] = Team('all', self.members)
    # Resolve resources
    for team in self.teams:
      if team.name in self.members_map:
        error_loc(team.loc, "team '%s' clashes with developer '%s'" % (team.name, team.name))
      for i, name in enumerate(team.members):
        if not isinstance(name, str):
          continue
        m = self.members_map.get(name)
        if m is None:
          error("no member with name '%s'" % name)
        team.members[i] = m

  def add_attrs(self, attrs):
    for k, v in attrs.items():
      setattr(self, k, v)
    self._recompute()

  def dump(self, p):
    p.writeln('= %s =\n' % self.name)
    for dev in self.members:
      dev.dump(p)
    for team in self.teams:
      team.dump(p)
