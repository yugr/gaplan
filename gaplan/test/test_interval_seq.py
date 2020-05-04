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
d5 = datetime.date(2020, 1, 5)
d6 = datetime.date(2020, 1, 6)

def test_add():
  seq = I.Seq([I.Interval(d1, d2),
               I.Interval(d5, d6)])
  seq.add(I.Interval(d3, d4))
  assert len(seq.ivs) == 3 and seq.ivs[1] == I.Interval(d3, d4)

  seq = I.Seq([I.Interval(d1, d2),
               I.Interval(d5, d6)])
  with pytest.raises(Exception):
    seq.add(I.Interval(d1, d2))

  seq = I.Seq([I.Interval(d1, d3),
               I.Interval(d5, d6)])
  with pytest.raises(Exception):
    seq.add(I.Interval(d2, d4))

  seq = I.Seq([I.Interval(d1, d2),
               I.Interval(d5, d6)])
  with pytest.raises(Exception):
    seq.add(I.Interval(d1, d3))

  seq = I.Seq([I.Interval(d1, d2),
               I.Interval(d3, d4)])
  seq.add(I.Interval(d5, d6))
  assert len(seq.ivs) == 3 and seq.ivs[2] == I.Interval(d5, d6)

  seq = I.Seq([I.Interval(d1, d2),
               I.Interval(d3, d4)])
  seq.add(I.Interval(d4, d6))
  assert len(seq.ivs) == 3 and seq.ivs[2] == I.Interval(d4, d6)
