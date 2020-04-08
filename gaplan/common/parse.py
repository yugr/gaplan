# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import datetime
import re

from gaplan.common.error import error_loc
from gaplan.common.ETA import ETA

class Location:
  def __init__(self, file, line):
    self.file = file
    self.line = line

  def prior(self):
    return Location(self.file, self.line - 1)

  def __str__(self):
    return '%s:%d' % (self.file, self.line)

# Not strictly a lexer but who cares
class Lexer:
  def __init__(self, file, lines=None):
    if lines is None:
      lines = open(file, 'r')

    # Strip comments
    lines = map(lambda s: re.sub(r'#.*$', '', s), lines)

    # And trailing whites
    lines = map(lambda s: s.rstrip(), lines)

    self.lines = list(lines)
    self.file = file
    self.loc = 1

  def __skip_empty(self):
    while self.lines and self.lines[0] == '':
      del self.lines[0]
      self.loc += 1

  def peek(self):
    self.__skip_empty()
    return (self.lines[0] if self.lines else None), Location(self.file, self.loc)

  def skip(self):
#    print("Lexer: skipping %s" % self.lines[0])
    del self.lines[0]
    self.loc += 1

def read_duration(s, loc):
  m = re.search(r'^\s*([0-9]+(?:\.[0-9]+)?)([hdwmy])\s*(.*)', s)
  if not m:
    error_loc(loc, 'failed to parse duration: %s' % s)
  d = float(m.group(1))
  spec = m.group(2)
  rest = m.group(3)
  if spec == 'd':
    d *= 8
  elif spec == 'w':
    d *= 5 * 8   # Work week
  elif spec == 'm':
    d *= 22 * 8   # Work month
  elif spec == 'y':
    d *= 12 * 22 * 8   # Work year
  d = int(round(d))
  return d, rest

def read_duration3(s, loc):
  # '1h' or '1h-3d' or '1h-3d (1d)'

  m, rest = read_duration(s, loc)

  M = m
  if rest and rest[0] == '-':
    M, rest = read_duration(rest[1:], loc)

  r = None
  if rest and rest[0] == '(':
    mm = re.search(r'\((.*)\)\s*$', rest)
    r, rest = read_duration(mm.group(1), loc)

  if rest:
    error_loc(loc, 'trailing chars: %s' % rest)

  return ETA(m, M, r)

def read_date(s, loc):
  # We could allow shorter formats (e.g. 'Jan 10')
  # but what if someone uses this in 2020?
  # TODO: allow UTC dates?
  m = re.search(r'^\s*([^-\s]*-[^-\s]*)(-[^-\s]*)?\s*(.*)', s)
  if not m:
    error_loc(loc, 'failed to parse date: %s' % s)
  date_str = m.group(1)
  # If day is omitted, consider first day
  date_str += m.group(2) or '-01'
  return datetime.datetime.strptime(date_str, '%Y-%m-%d'), m.group(3)

# TODO: parse UTC times i.e. 2015-02-01T12:00 ?
def read_date2(s, loc):
  # '2015-02-01' or '2015-02-01 - 2015-02-03'

  start, rest = read_date(s, loc)

  finish = start
  if rest and rest[0] == '-':
    finish, rest = read_date(rest[1:], loc)

  return start, finish
