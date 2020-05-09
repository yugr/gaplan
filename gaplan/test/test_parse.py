# The MIT License (MIT)
# 
# Copyright (c) 2018 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import pytest

import gaplan.common.parse as PA

def test_read_effort():
  d, rest = PA.read_effort('0.5d___', None)
  assert d == 4 and rest == '___'

def test_read_effort2():
  d = PA.read_eta('0.5d-1w (10%, 2d)', None)
  assert d.min == 4 and d.max == 40 and d.real == 16 and abs(d.completion - 0.1) < 0.01
