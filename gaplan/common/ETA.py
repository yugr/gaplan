# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# This file contains classes which describe effort estimates.

from gaplan.common.error import error

from enum import IntEnum, unique

@unique
class Bias(IntEnum):
  WORST_CASE = 1
  PESSIMIST  = 2
  NONE       = 3
  OPTIMIST   = 4
  BEST_CASE  = 5
  COUNT      = 6

  @staticmethod
  def worse(bias):
    if bias == Bias.WORST_CASE:
      return bias
    return Bias(bias - 1)

_bias = Bias.NONE

# This class holds min and max effort + an optional actual effort.
class ETA:
  """This class holds optimistic and perssimistic effort estimates
     and tracking data."""

  def __init__(self, min=None, max=None, real=None, completion=0):
    self.min = min
    self.max = max
    self.real = real
    self.completion = completion

  def estimate(self, risk=None):
    if self.min is None or self.max is None:
      return None, None

    # Calibrate bias based on risk
    bias = _bias
    if risk is not None:
      for _ in range(risk - 1):
        bias = Bias.worse(bias)

    k = {
      Bias.WORST_CASE : 0,
      Bias.PESSIMIST  : 1.0 / 3,
      Bias.NONE       : 0.5,
      Bias.OPTIMIST   : 2.0 / 3,
      Bias.BEST_CASE  : 1}[bias]
    avg = k * self.min + (1 - k) * self.max

    # "2 sigma rule"
    dev = (self.max - self.min) / 4

    return avg, dev

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

def set_options(**kwargs):
  for k, v in kwargs.items():
    if k == 'estimate_bias':
      try:
        global _bias
        _bias = Bias[v.upper().replace('-', '_')]
      except KeyError:
        error("unknown bias value '%s'" % v)
    else:
      error("ETA: unknown option: " + k)
