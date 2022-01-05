# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Effort estimation strategies."""

from enum import IntEnum, unique

@unique
class Bias(IntEnum):
  """Estimation bias."""

  WORST_CASE = 1
  PESSIMIST  = 2
  NONE       = 3
  OPTIMIST   = 4
  BEST_CASE  = 5

  @staticmethod
  def worse(bias):
    """Returns next more pessimistic bias."""
    if bias == Bias.WORST_CASE:
      return bias
    return Bias(bias - 1)

_bias = Bias.NONE

class BaseEstimator:
  """Base estimation strategy.

     This strategy averages estimates based on bias.
  """

  def __init__(self, bias=Bias.NONE):
    bias_map = {
      Bias.WORST_CASE : 0,
      Bias.PESSIMIST  : 1.0 / 3,
      Bias.NONE       : 0.5,
      Bias.OPTIMIST   : 2.0 / 3,
      Bias.BEST_CASE  : 1}
    self.bias = bias
    self.p = bias_map[bias]
    self.q = 1 - self.p

  def probs(self, goal):
    """Returns probabilities of pessimistic/optimistic estimates."""
    return self.p, self.q

  def estimate(self, act):
    """Returns single-point estimate of action's effort."""

    effort = act.effort
    if effort.min is None or effort.max is None:
      return None, None

    p, q = self.probs(act.tail)
    avg = p * effort.min + q * effort.max

    # "2 sigma rule"
    dev = (effort.max - effort.min) / 4

    return avg, dev

class RiskBasedEstimator(BaseEstimator):
  """Risk-base estimator.

     This estimator pessimizes estimates for risky goals.
  """

  def __init__(self, bias):
    super().__init__(bias)
    self.estimators = {}
    self.estimators = {b: BaseEstimator(b) for b in Bias}

  def probs(self, goal):
    bias = self.bias
    if goal is not None and goal.risk is not None:
      for _ in range(goal.risk - 1):
        bias = Bias.worse(bias)
    return self.estimators[bias].probs(goal)
