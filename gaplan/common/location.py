# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Source file locations."""

class Location:
  """Location in file."""

  def __init__(self, filename=None, lineno=None):
    self.filename = filename
    self.lineno = lineno

  def prior(self):
    """Location of preceeding line."""
    return Location(self.filename, self.lineno - 1) if self else self

  def __str__(self):
    if not self:
      return '?:?'
    return f'{self.filename}:{self.lineno}'

  def __bool__(self):
    return self.filename is not None
