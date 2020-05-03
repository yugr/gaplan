# The MIT License (MIT)
# 
# Copyright (c) 2018 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import pytest

from gaplan.common import parse as PA

def test_read_effort():
  d, rest = PA.read_effort('0.5d___', None)
  assert d == 4 and rest == '___'
