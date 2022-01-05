# The MIT License (MIT)
# 
# Copyright (c) 2018-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Common parsing functions."""

import datetime
import re
import sys

from gaplan.common.error import error, error_if
from gaplan.common.ETA import ETA
from gaplan.common.location import Location
import gaplan.common.interval as I
import gaplan.common.matcher as M

def read_fraction(s, loc):
  if M.search(r'^[0-9.]+$', s):
    return float(s)
  if M.search(r'^([0-9]+)%$', s):
    return int(M.group(1)) / 100
  error(loc, f"unexpected fraction syntax: {s}")

def read_effort(s, loc):
  """Parse effort estimate e.g. "1h" or "3d"."""
  m = re.search(r'^\s*([0-9]+(?:\.[0-9]+)?)([hdwmy])\s*(.*)', s)
  error_if(m is None, f"failed to parse effort: {s}")
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

def read_eta(s, loc):
  """Parse effort estimate e.g. "1h", "1h-3d" or "1h-3d (1d)"."""

  min, rest = read_effort(s, loc)

  max = min
  if rest and rest[0] == '-':
    max, rest = read_effort(rest[1:], loc)

  real = None
  completion = 0
  if M.search(r'^\s*\((.*)\)\s*$', rest):
    for a in re.split(r'\s*,\s*', M.group(1)):
      if re.search(r'^[0-9.]+[hdwmy]', a):
        real, _ = read_effort(a, loc)
      elif M.search(r'^([0-9]+)%', a):
        completion = float(M.group(1)) / 100
      else:
        error(loc, f"unknown ETA attribute: {a}")

  return ETA(min, max, real, completion)

def read_date(s, loc):
  """Parse date duration e.g. "2020-01-10"."""
  # TODO: allow shorter formats (e.g. 'Jan 10')
  # but what if someone uses this in 2020?!
  m = re.search(r'^\s*([^-\s]*-[^-\s]*)(-[^-\s]*)?\s*(.*)', s)
  error_if(m is None, loc, f"failed to parse date: {s}")
  date_str = m.group(1)
  # If day is omitted, consider first day
  date_str += m.group(2) or '-01'
  return datetime.datetime.strptime(date_str, '%Y-%m-%d').date(), m.group(3)

def read_float(s, loc):
  """Parse float number."""
  m = re.search(r'^\s*([0-9]+(\.[0-9]+)?)(.*)', s)
  error_if(m is None, loc, f"failed to parse float: {s}")
  return float(m.group(1)), m.group(3)

# TODO: parse UTC times i.e. 2015-02-01T12:00 ?
def read_date2(s, loc):
  """Parse date duration e.g. "2015-02-01" or "2015-02-01 - 2015-02-03"."""
  start, rest = read_date(s, loc)
  finish = start
  if rest and rest[0] == '-':
    finish, rest = read_date(rest[1:], loc)
  return I.Interval(start, finish, True)

def read_par(s):
  """Parse parallel directive e.g. "|| 3"."""
  m = re.match(r'^\|\|(\s*([0-9]+))?$', s)
  return int(m.group(2) or sys.maxsize)

def read_alloc(a, loc):
  """Parse allocation directive e.g. "@dev1/dev2 (dev3)"."""
  aa = a.split('(')
  if len(aa) > 2 or not M.search(r'^@\s*(.*)', aa[0]):
    error(loc, f"unexpected allocation syntax: {a}")
  alloc = M.group(1).strip().split('/')
  if len(aa) <= 1:
    real_alloc = []
  else:
    if not M.search(r'^([^)]*)\)', a):
      error(loc, f"unexpected allocation syntax: {a}")
    real_alloc = M.group(1).strip().split('/')
  return alloc, real_alloc

class Lexeme:
  """Represents parsed lexeme."""

  def __init__(self, type, data, text, loc):
    self.type = type
    self.data = data
    self.loc = loc
    self.text = text

  def __repr__(self):
    return f'{self.loc}: {self.type}: {self.data}'

class BaseLexer:
  """Base class for lexers."""

  def __init__(self):
    self.lexemes = []
    self.filename = self.line = self.lineno = None

  def _loc(self):
    return Location(self.filename, self.lineno)

  def loc(self):
    """Location of next lexeme."""
    if not self.lexemes:
      self.peek()
    return Location(self.filename, self.lineno)

  # Override in children
  def reset(self, filename, lines):
    """Resets lexer state."""
    self.filename = filename
    self.lineno = 0
    self.line = ''
    self.lines = lines

  # Override in children
  def update_on_newline(self):
    """Update state on newline."""
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
    """Return next lexeme without advancing lexeme."""
    if not self.lexemes:
      self.__skip_empty()
      self.next_internal()
    if not self.lexemes:
      return None
    l = self.lexemes[0]
    return l

  def skip(self):
    """Advance to next lexeme."""
    del self.lexemes[0]

  def next(self):
    """Return current lexeme and advance to next."""
    l = self.peek()
    if l is not None:
      self.skip()
    return l

  def next_if(self, type):
    """Return current lexeme and advance if type matches."""
    l = self.peek()
    if l is None:
      return None
    if l.type in type if isinstance(type, list) else l.type == type:
      self.skip()
      return l

  def expect(self, type):
    """Return current lexeme and advance if type matches."""
    l = self.next()
    if isinstance(type, list):
      if l.type not in type:
        type_str = ', '.join(map(lambda t: f"'{type}'"))
        error(l.loc, f"expecting '{type_str}', got '{l.type}'")
    elif l.type != type:
      error(l.loc, f"expecting '{type}', got '{l.type}'")
    return l

class BaseParser:
  def __init__(self, lex):
    """Base class for parsers."""
    self.lex = lex

  # Override in children
  def reset(self, filename, f):
    """Resets lexer's state."""
    self.lex.reset(filename, f)

  # Override in children
  def parse(self, W):
    return None
