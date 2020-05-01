# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import pytest
import datetime

def test_before():
  d1 = datetime.date(2020, 1, 1)
  d2 = datetime.date(2020, 1, 2)
  d3 = datetime.date(2020, 1, 3)
  assert I.Interval(d1, d2).before(I.Interval(d2, d3))
  assert not I.Interval(d1, d2).before(I.Interval(d1, d2))
  assert not I.Interval(d2, d3).before(I.Interval(d1, d2))

def test_after():
  d1 = datetime.date(2020, 1, 1)
  d2 = datetime.date(2020, 1, 2)
  d3 = datetime.date(2020, 1, 3)
  assert I.Interval(d2, d3).before(I.Interval(d1, d2))
  assert not I.Interval(d1, d2).before(I.Interval(d1, d2))
  assert not I.Interval(d1, d2).before(I.Interval(d2, d3))

def test_overlap():
  d1 = datetime.date(2020, 1, 1)
  d2 = datetime.date(2020, 1, 2)
  d3 = datetime.date(2020, 1, 3)
  d4 = datetime.date(2020, 1, 4)
  assert I.Interval(d1, d3).before(I.Interval(d2, d4)
  assert not I.Interval(d1, d2).before(I.Interval(d3, d4))

def test_union():
  d1 = datetime.date(2020, 1, 1)
  d2 = datetime.date(2020, 1, 2)
  d3 = datetime.date(2020, 1, 3)
  d4 = datetime.date(2020, 1, 4)
  assert I.Interval(d1, d3).union(I.Interval(d2, d4)) == I.Interval(d1, d4)
  assert I.Interval(d1, d2).union(I.Interval(d3, d4)) is None
