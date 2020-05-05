# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import pytest
import datetime

from gaplan.common import interval as I

d1 = datetime.date(2020, 1, 1)
d2 = datetime.date(2020, 1, 2)
d3 = datetime.date(2020, 1, 3)
d4 = datetime.date(2020, 1, 4)

def test_create():
  with pytest.raises(Exception):
    I.Interval(d2, d1)

def test_before():
  assert I.Interval(d1, d2).before(I.Interval(d2, d3))
  assert not I.Interval(d1, d2).before(I.Interval(d1, d2))
  assert not I.Interval(d2, d3).before(I.Interval(d1, d2))

def test_after():
  assert I.Interval(d2, d3).after(I.Interval(d1, d2))
  assert not I.Interval(d1, d2).after(I.Interval(d1, d2))
  assert not I.Interval(d1, d2).after(I.Interval(d2, d3))

def test_overlaps():
  assert I.Interval(d1, d3).overlaps(I.Interval(d2, d4)
  assert not I.Interval(d1, d2).overlaps(I.Interval(d3, d4))

def test_union():
  assert I.Interval(d1, d3).union(I.Interval(d2, d4)) == I.Interval(d1, d4)
  assert I.Interval(d1, d2).union(I.Interval(d3, d4)) is None
