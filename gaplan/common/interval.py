# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

from gaplan.common import printers as PR

import sys
import datetime

class Interval:
  def __init__(self, l, r=None):
    assert isinstance(l, datetime.datetime)
    self.l = l
    self.r = r or l

  @staticmethod
  def top():
    return Interval(sys.maxsize, 0)

  @staticmethod
  def bot():
    return Interval(-sys.maxsize, 0)

  @property
  def start(self):
    return self.l

  @property
  def finish(self):
    return self.r

  @property
  def length(self):
    return self.r - self.l

  def before(self, i):
    return self.r <= i.l

  def after(self, i):
    return self.l >= i.r

  def intersects(self, i):
    return not (self.before(i) or self.after(i))

  def union(self, i):
    return Interval(min(self.l, i.l), max(self.r, i.r))

  def __str__(self):
    return '[%s, %s)' % (PR.print_date(self.l), PR.print_date(self.r))
