# The MIT License (MIT)
# 
# Copyright (c) 2018-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Pretty-printing APIs."""

import sys

class SourcePrinter:
  """Formatting printer."""

  def __init__(self, out=sys.stdout, tab='  '):
    self.out = out
    self.tabs = ['']
    self.tab = tab
    self.idx = 0

  def enter(self):
    self.idx += 1
    if self.idx >= len(self.tabs):
      self.tabs.append(self.tabs[-1] + self.tab)
    assert self.idx < len(self.tabs)
    return self

  def exit(self):
    self.idx -= 1
    assert self.idx >= 0

  def __enter__(self):
    return self.enter()

  def __exit__(self, type, value, traceback):
    return self.exit()

  def write(self, s):
    s = str(s)
    ss = s.split('\n')
    if not ss[-1]:
      ss = ss[:-1]
    tab = self.tabs[self.idx]
    tab_nl = '\n' + tab
    self.out.write(tab + tab_nl.join(ss) + '\n')

  def writeln(self, s):
    s = str(s)
    self.write(s + '\n')
