# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""PERT diagram plotter for declarative plans."""

import subprocess
import io

from gaplan.common.error import error
import gaplan.common.printers as PR
from gaplan.common import platform

def _get_node_colors(g):
  if g.is_completed():
    return 'gray', 'slategray'
  if g.prio is not None and g.prio > 2:
    return 'red', 'black'
  return 'black', 'black'

def _get_node_label(g, visible=False):
  # Do not show fake names
  if g.dummy and visible:
    return ''

  caps = [g.name, ' (']
  caps.append('%d%%' % g.complete())
  if g.deadline:
    caps.append(', ' + g.deadline.strftime('%b %d'))
  caps.append(')')

#  if g.tasks:
#    caps.append('\\n' + '/'.join(g.tasks))

  return ''.join(caps)

def _print_node(g, p):
  box_color, text_color = _get_node_colors(g)
  p.writeln('"%s" [ label="%s", color=%s, fontcolor = %s ];'
            % (_get_node_label(g),
               _get_node_label(g, True),
               box_color, text_color))

def _print_node_edges(g, p):
  cap = _get_node_label(g)
  for act in g.preds:
    if act.head:
      p.writeln('"%s" -> "%s";' % (_get_node_label(act.head), cap))

  while g is not None:
    for act in g.global_preds:
      if act.head:
        p.writeln('"%s" -> "%s";' % (_get_node_label(act.head), cap))
    g = g.parent

def export(net, dump=False):
  """Generate PERT chart in Graphviz from declarative plan."""

  p = PR.SourcePrinter(io.StringIO())

  p.writeln('digraph G {')
  with p:
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
