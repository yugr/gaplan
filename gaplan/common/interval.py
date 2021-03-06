# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""APIs for describing and operating on time ranges."""

import datetime

class Interval:
  """Represents interval of time."""

  def __init__(self, l, r=None, closed=False):
    assert isinstance(l, datetime.date)
    self.l = l
    self.r = r or l
    if self.r < self.l:
      raise Exception(f"Trying to create invalid interval {self}")
    if closed:
      self.r += datetime.timedelta(days=1)

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
    """Does interval lie on the left of another?"""
    return self.r <= i.l

  def after(self, i):
    """Does interval lie on the right of another?"""
    return self.l >= i.r

  def overlaps(self, i):
    """Do intervals overlap?"""
    return not (self.before(i) or self.after(i))

  def union(self, i):
    """Union of intervals."""
    if i.l < self.l:
      return i.union(self)
    if self.r < i.l:
      return None
    return Interval(min(self.l, i.l), max(self.r, i.r))

  def __eq__(self, i):
    return self.l == i.l and self.r == i.r

  def __repr__(self):
    return f'[{self.l}, {self.r})'

class Seq:
  """A sorted sequence of non-intersecting intervals
     for efficient date queries."""

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

  def _find_date(self, d):
    # Invariant
    #   i < l, ivs[i].finish <= d
    #   i > r, d < ivs[i].start

    l, r = 0, len(self.ivs) - 1
    hit = False
    while l <= r:
      m = int((l + r) / 2)
      IV = self.ivs[m]
      if IV.finish <= d:
        l = m + 1
      elif d < IV.start:
        r = m - 1
      else:
        l = m
        hit = True
        break

    return l, hit

  def add(self, iv):
    """Insert interval into table."""

    # Search position by starting point of interval
    i, hit = self._find_date(iv.start)

    if not hit and i < len(self.ivs):
      iv_next = self.ivs[i]
      if iv.finish > iv_next.start:
        hit = True

    if hit:
      raise Exception(f"Inserting overlapping interval {iv} into {self}")

    self.ivs.insert(i, iv)

  def update(self, ivs):
    """Insert intervals into table."""
    for iv in ivs:
      self.add(iv)

  def contains(self, d):
    """Does date belong to interval?"""
    _, hit = self._find_date(d)
    return hit

  def __repr__(self):
    return ', '.join(str(iv) for iv in self.ivs)
