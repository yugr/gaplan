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
  def __init__(self, filename, lineno):
    self.filename = filename
    self.lineno = lineno

  def prior(self):
    return Location(self.filename, self.lineno - 1)

  def __str__(self):
    return '%s:%d' % (self.filename, self.lineno)

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

class BaseLexer:
  def __init__(self, v=0):
    self.lexemes = []
    self.filename = self.line = self.lineno = None
    self.v = v

  def _loc(self):
    return Location(self.filename, self.lineno)

  def loc(self):
    if not self.lexemes:
      self.peek()
    return Location(self.filename, self.lineno)

  # Override in children
  def reset(self, filename, lines):
    self.filename = filename
    self.lineno = 0
    self.line = ''
    self.lines = lines

  # Override in children
  def update_on_newline(self):
    pass

  # Override in children
  def next_internal(self):
    return None

  def __skip_empty(self):
    while self.line == '' and self.lines:
      next_line = next(self.lines, None)
      if next_line is None:
        break
      self.line = next_line
      self.lineno += 1
      self.update_on_newline()

  def peek(self):
    if not self.lexemes:
      self.__skip_empty()
      self.next_internal()
    if not self.lexemes:
      return None
    l = self.lexemes[0]
    return l

  def skip(self):
    del self.lexemes[0]

  def next(self):
    l = self.peek()
    if l is not None:
      self.skip()
    return l

  def next_if(self, type):
    l = self.peek()
    if l is None:
      return None
    if l.type in type if isinstance(type, list) else l.type == type:
      self.skip()
      return l

  def expect(self, type):
    l = self.next()
    if isinstance(type, list):
      if l.type not in type:
        type_str = ', '.join(map(lambda t: '\'%s\'' % t, type))
        error_loc(l.loc, "expecting %s, got '%s'" % (type_str, l.type))
    elif l.type != type:
      error_loc(l.loc, "expecting '%s', got '%s'" % (type, l.type))
    return l

class BaseParser:
  def __init__(self, lex, v=0):
    self.v = v
    self.lex = lex

  def _dbg(self, msg, v=1):
    if self.v >= v:
      print(msg)

  # Override in children
  def reset(self, filename, f):
    self.lex.reset(filename, f)

  # Override in children
  def parse(self, filename, f):
    return None
