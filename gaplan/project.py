# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""APIs for dealing with organizational aspects of plan: teams, resources, etc."""

import datetime

from gaplan.common.error import error, error_if
import gaplan.common.parse as P
import gaplan.common.matcher as M
import gaplan.common.interval as I

class Resource:
  """Describes a single developer."""

  def __init__(self, name, loc):
    self.name = name
    self.efficiency = 1.0
    self.loc = loc
    self.vacations = []

  def add_attrs(self, attrs, loc):
    for a in attrs:
      if M.search(r'^[0-9.]+$', a):
        self.efficiency = float(a)
      elif M.search(r'vacations?\s+(.*)', a):
        duration = P.read_date2(M.group(1), loc)
        self.vacations.append(duration)
      else:
        error(loc, "unexpected resource attribute: %s" % a)

  def dump(self, p):
    p.writeln("Developer %s (%s, %f)" % (self.name, self.loc, self.efficiency))
    vv = []
    for iv in self.vacations:
      vv.append('%s' % iv)
    p.writeln("  vacations: %s" % ', '.join(vv))

class Team:
  """Describes a team of developers."""

  def __init__(self, name, members, loc):
    self.name = name
    self.members = members
    self.loc = loc

  def dump(self, p):
    p.writeln("Team %s (%s):" % (self.name, self.loc))
    p.enter()
    for rc in self.members:
      rc.dump(p)
    p.exit()

class Project:
  """Describes project resources."""

  def __init__(self, loc):
    self.name = 'Unknown'
    self.loc = loc
    year = datetime.date.today().year
    self.duration = I.Interval(datetime.date(year, 1, 1),
                               datetime.date(year, 12, 31), True)
    self.members = []
    self.members_map = {}
    self.teams = {}
    self.teams_map = {}
    self.holidays = []
    self.tracker_link = 'http://jira.localhost/browse/%s'
    self.pr_link = None

  def _recompute(self):
    self.members_map = {m.name : m for m in self.members}
    self.teams_map = {t.name : t for t in self.teams}
    if 'all' in self.teams_map:
      error(self.teams_map['all'].loc, "predefined goal 'all' overriden")
    self.teams_map['all'] = Team('all', self.members, self.loc)
    # Resolve resources
    for team in self.teams:
      error_if(team.name in self.members_map, team.loc,
               "team '%s' clashes with developer '%s'" % (team.name, team.name))
      for i, name in enumerate(team.members):
        if not isinstance(name, str):
          continue
        m = self.members_map.get(name)
        error_if(m is None, team.loc, "no member with name '%s'" % name)
        team.members[i] = m

  def add_attrs(self, attrs):
    for k, v in attrs.items():
      setattr(self, k, v)
    self._recompute()

  def get_resources(self, names):
    """Returns resources that match a set of team/resource names."""
    resources = []
    for name in names:
      team = self.teams_map.get(name)
      if team is not None:
        for rc in team.members:
          if rc not in resources:
            resources.append(rc)
      else:
        rc = self.members_map.get(name)
        error_if(rc is None, "resource '%s' not defined" % name)
        if rc not in resources:
          resources.append(rc)
    resources = sorted(resources, key=lambda rc: rc.name)
    return resources

  def dump(self, p):
    p.writeln("= Project '%s' at %s =\n" % (self.name, self.loc))

    p.writeln("Resources:")
    with p:
      for dev in self.members:
        dev.dump(p)
    p.writeln("")

    p.writeln("Teams:")
    with p:
      for team in self.teams:
        team.dump(p)
    p.writeln("")

    p.writeln("Vacations:")
    with p:
      for duration in self.holidays:
        p.writeln(duration)
    p.writeln("")
