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
from gaplan.common import matcher as M

class Resource:
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
