# The MIT License (MIT)
# 
# Copyright (c) 2018-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""Burndown chart plotter for declarative plans."""

import datetime
import io
from collections import defaultdict

import gaplan.goal as G
import gaplan.common.printers as PR

def export(net, goal, duration, dump):
  """Generate gnuplot chart for all children of goal within time interval."""

  counts = defaultdict(int)
  counts[duration.start] = 0
  partial = [0]
  total_children = [0]
  def scan_completed(g):
    total_children[0] += 1   # TODO: skip milestones?
    if g.is_completed() and g.is_scheduled():
      counts[g.completion_date] += 1
    else:
      partial[0] += g.complete() / 100.0
  G.visit_goals([goal], callback=scan_completed, hierarchical=True)

  # Also count partially completed tasks
  today = datetime.date.today()
  if today < duration.finish:
    counts[today] = int(partial[0])

  sorted_dates = sorted(counts.keys())

  prev = 0
  for date in sorted_dates:
    counts[date] += prev
    prev = counts[date]

  p = PR.SourcePrinter(io.StringIO())

  p.writeln('set terminal png')

  p.write(f'''
reset

set title "{goal.name} (burndown chart)"
set timefmt "%Y-%m-%d"

set xlabel "Days"
set format x "%b-%d"
set xdata time
set xrange ["{duration.start}":"{duration.finish}"]
set xtics nomirror

set ylabel "#Goals"
set yrange [0:{total_children[0]}]
set ytics mirror

plot "-" using 1:2 title 'Real' with lines, "-" using 1:2 title "Planned" with lines
''')

  for date in sorted_dates:
    n = counts[date]
    p.writeln('  %s %d' % (date, total_children[0] - n))
  p.writeln('e')

  p.writeln('  %s %d' % (duration.start, total_children[0]))
  p.writeln('  %s %d' % (duration.finish, 0))
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
