# The MIT License (MIT)
# 
# Copyright (c) 2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# This file holds class for describing position in source file.

class Location:
  def __init__(self, filename=None, lineno=None):
    self.filename = filename
    self.lineno = lineno

  def prior(self):
    return Location(self.filename, self.lineno - 1) if self else self

  def __str__(self):
    if not self:
      return '?:?'
    return '%s:%d' % (self.filename, self.lineno)

  def __bool__(self):
    return self.filename is not None
