# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import datetime
import io
from collections import defaultdict

from gaplan import goal as G
from gaplan.common import printers as PR

def export(net, goal, start_date, finish_date, dump):
  counts = defaultdict(int)
  counts[start_date] = 0
  partial = [0]
  total_children = [0]
  def scan_completed(g):
    total_children[0] += 1   # TODO: skip milestones?
    if g.is_completed() and g.is_scheduled():
      counts[g.finish_date] += 1
    else:
      partial[0] += g.complete() / 100.0
  G.visit_goals([goal], callback=scan_completed, hierarchical=True)

  # Also count partially completed tasks
  today = datetime.datetime.now()
  if today < finish_date:
    counts[today] = int(partial[0])

  sorted_dates = sorted(counts.keys())

  prev = 0
  for date in sorted_dates:
    counts[date] += prev
    prev = counts[date]

  p = PR.SourcePrinter(io.StringIO())

  p.writeln('set terminal png')

  p.write('''
reset

set title "%s (burndown chart)"
set timefmt "%%Y-%%m-%%d"

set xlabel "Days"
set format x "%%b-%%d"
set xdata time
set xrange ["%s":"%s"]
set xtics nomirror

set ylabel "#Goals"
set yrange [0:%d]
set ytics mirror

plot "-" using 1:2 title 'Real' with lines, "-" using 1:2 title "Planned" with lines
''' % (goal.name, start_date, finish_date, total_children[0]))

  for date in sorted_dates:
    n = counts[date]
    p.writeln('  %s %d' % (PR.print_date(date), total_children[0] - n))
  p.writeln('e')

  p.writeln('  %s %d' % (PR.print_date(start_date), total_children[0]))
  p.writeln('  %s %d' % (PR.print_date(finish_date), 0))
  p.writeln('e')

  if dump:
    print(p.out.getvalue())
  else:
    png_file = 'burndown.png'

    try:
      with open(png_file, 'w') as f:
        if 0 != subprocess.call(['gnuplot', '-'], stdin=p.out, stdout=f):
          error("failed to run gnuplot(1); do you have Gnuplot installed?")
    except FileNotFoundError:
      error("gnuplot program not found; do you have Gnuplot installed?")

    platform.open_file(png_file)
