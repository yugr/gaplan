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
from . import goal as G
from . import resource

class ProjectInfo:
  def __init__(self):
    self.name = 'Unknown'
    year = datetime.datetime.today().year
    self.start = datetime.date(year, 1, 1)
    self.finish = datetime.date(year, 12, 31)
    self.members = []
    self.tracker_link = 'http://jira.localhost/browse/%s'
    self.pr_link = None

  def add_attrs(self, attrs):
    for k, v in attrs.items():
      setattr(self, k, v)

  def dump(self, p):
    p.writeln('= %s =\n' % self.name)
    for dev in self.members:
      dev.dump(p)
