# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""This file contains class which describes effort estimates and actuals."""

from gaplan.common.error import error

# This class holds min and max effort + an optional actual effort.
class ETA:
  """This class holds optimistic and pessimistic effort estimates
     and tracking data."""

  def __init__(self, min=None, max=None, real=None, completion=0):
    self.min = min
    self.max = max
    self.real = real
    self.completion = completion

  def defined(self):
    return self.min is not None or self.real is not None

  def __add__(self, x):
    if self.real is not None or x.real is None \
        or self.completion and x.completion:
      real = None
      completion = 0
    else:
      real = self.real + x.real 
      completion = 0
    return ETA(self.min + x.min, self.max + x.max, real, completion)

  def __mul__(self, k):
    return ETA(self.min * k,
               self.max * k,
               None if self.real is None else self.real * k,
               self.completion)

  def __repr__(self):
    if self.min is None \
        and self.max is None \
        and self.real is None:
      return ''
    min_s = '?' if self.min is None else str(self.min)
    max_s = '?' if self.max is None else str(self.max)
    real_s = '?' if self.real is None else str(self.real)
    if min_s == max_s:
      return '%sh (%sh, %g%%)' % (min_s, real_s, self.completion)
    return '%sh-%sh (%sh, %g%%)' % (min_s, max_s, real_s, self.completion)
