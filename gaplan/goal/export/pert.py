# The MIT License (MIT)
# 
# Copyright (c) 2016-2018 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import subprocess
import io
import sys
import os

from gaplan.common.error import error, warn
from gaplan.common import printers as PR
from gaplan.common import platform

def _get_node_colors(g):
  if g.is_completed():
    return 'gray', 'slategray'
  if g.prio is not None and g.prio > 2:
    return 'red', 'black'
  return 'black', 'black'

def _get_node_caption(g):
  cap = g.name

  cap += ' (%d%%' % g.complete()
  if g.deadline:
    cap += ', ' + g.deadline.strftime('%b %d')
  cap += ')'

#  if g.tasks:
#    cap += '\\n' + '/'.join(g.tasks)

  return cap

def _print_node(g, p):
  box_color, text_color = _get_node_colors(g)
  p.writeln('"%s" [ color=%s, fontcolor = %s ];' % (_get_node_caption(g), box_color, text_color))

def _print_node_edges(g, p):
  cap = _get_node_caption(g)
  for act in g.preds:
    if act.head:
      p.writeln('"%s" -> "%s";' % (_get_node_caption(act.head), cap))

  while g is not None:
    for act in g.global_preds:
      if act.head:
        p.writeln('"%s" -> "%s";' % (_get_node_caption(act.head), cap))
    g = g.parent

def export(net, dump=False):
  p = PR.SourcePrinter(io.StringIO())

  p.writeln('digraph G {')
  with p as p:
    p.write('''\
#graph [rankdir = LR, splines = ortho]
#graph [rankdir = LR, concentrate = true]
graph [rankdir = LR]
''')
    net.visit_goals(callback=lambda g: _print_node(g, p))
    p.writeln('')
    net.visit_goals(callback=lambda g: _print_node_edges(g, p))
  p.writeln('}')

  if dump:
    print(p.out.getvalue())
  else:
    gv_file = 'pert.gv'
    pdf_file = 'pert.pdf'

    with open(gv_file, 'wt') as out:
      out.write(p.out.getvalue())

    try:
      if 0 != subprocess.call(['dot', '-Tpdf', gv_file], stdout=open(pdf_file, 'wb')):
        error("failed to run dot(1); do you have Graphviz installed?")
    except FileNotFoundError:
      error("dot program not found; do you have Graphviz installed?")

    platform.open_file(pdf_file)
