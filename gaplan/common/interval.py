# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# This file contains APIs for describing and operating on time ranges.

from gaplan.common import printers as PR

import sys
import datetime

class Interval:
  """Represents interval of time."""

  def __init__(self, l, r=None):
    assert isinstance(l, datetime.datetime)
    self.l = l
    self.r = r or l

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

  def overlaps(self, i):
    return not (self.before(i) or self.after(i))

  def union(self, i):
    if i.l < self.l:
      return i.union(self)
    if self.r < i.l:
      return None
    return Interval(min(self.l, i.l), max(self.r, i.r))

  def __eq__(self, i):
    return self.l == i.l and self.r == i.r

  def __str__(self):
    return '[%s, %s)' % (PR.print_date(self.l), PR.print_date(self.r))

class Seq:
  """A sorted sequence of non-intersecting intervals for efficient queries."""

  def __init__(self, ivs):
    self.ivs = []
    if ivs:
      # Merge and sort intervals
      ivs = sorted(ivs, key=lambda iv: iv.start)
      last = ivs[0]
      for iv in ivs[1:]:
        last_ = last.union(iv)
        if last_ is not None:
          last = last_
          continue
        self.ivs.append(last)
        last = iv
      self.ivs.append(last)

  def add(self, iv):
    # Search position by starting point of interval
    #
    # Invariant
    #   i < l, ivs[i].finish <= iv.start
    #   i > r, ivs[i].start > iv.start

    start = iv.l
    l, r = 0, len(self.ivs) - 1
    while l <= r:
      m = int((l + r) / 2)
      IV = self.ivs[m]
      if IV.finish <= start:
        l = m + 1
      elif start < IV.start:
        r = m - 1
      else:
        raise Exception("Inserting overlapping interval %s into %s" % (iv, self))

    # Insert new interval

    self.ivs.insert(l, iv)

  def update(self, ivs):
    for iv in ivs:
      self.add(iv)

  def __str__(self):
    return ', '.join(str(iv) for iv in self.ivs)
