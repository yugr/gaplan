#!/usr/bin/env python2.7

# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.
#
# Main driver for Gaplan project
# Run with --help for details.

import sys
import argparse

from gaplan.common.error import error, error_if, set_basename, set_options
import gaplan.common.interval as I
from gaplan.common import ETA
import gaplan.common.printers as PR
import gaplan.parse as PA
import gaplan.goal as G
import gaplan.wbs as WBS
import gaplan.schedule as S
import gaplan.estimator as E

from gaplan.export import pert
from gaplan.export import tj
from gaplan.export import msp
from gaplan.export import burn

def main():
  set_basename('gaplan')

  parser = argparse.ArgumentParser(
    formatter_class=argparse.RawDescriptionHelpFormatter,
    description="A toolset for working with declarative plans (google 'Gaperton notepad' for more details).",
    epilog="""\

ACTION should be one of
  dump      Dumps plan (useful for debugging).
  tj        Convert declarative plan to TaskJuggler project.
  pert      Plot a netchart ("PERT diagram").
  burn      Print a burndown chart.
  msp       Convert declarative plan to MS Project project (TBD!).
  schedule  Generate simple schedule.

Examples:
  Pretty print PERT diagram:
  $ {exe} dump plan.txt

  Generate PERT diagram via GraphViz:
  $ {exe} pert plan.txt | dot -Tpdf > plan.pdf

  Pretty print WBS:
  $ {exe} dump-wbs plan.txt

  Generate TaskJuggler project and report:
  $ {exe} tj plan.txt > plan.tjp
  $ mkdir -p tjdir
  $ tj3 plan.tjp -o tjdir

  Generate burndown chart:
  $ (echo 'set terminal png; {exe} --phase 'Iteration 1 completed' burndown plan.txt) | gnuplot - > burndown.png\
""".format(exe='python -mgaplan'))
  parser.add_argument(
    'action',
    metavar='ACT',
    help="Action performed on PLAN.",
    choices=['dump', 'dump-wbs', 'tj', 'msp', 'pert', 'burn', 'burndown', 'schedule'])
  parser.add_argument(
    'plan',
    metavar='PLAN',
    help="Path to declarative plan.",
    nargs='?')
  parser.add_argument(
    '-o', '--only',
    help="Limit output to a particular goal and it's predecessors.")
  parser.add_argument(
    '-b', '--bias',
    help="Estimation bias.",
    choices=['none', 'pessimist', 'optimist', 'worst-case', 'best-case'],
    default='none')
  parser.add_argument(
    '--iter', '-i',
    help="Iteration to use for burndown chart.")
  parser.add_argument(
    '-W',
    help="Enable extra warnings.",
    action='count',
    default=0)
  parser.add_argument(
    '-v',
    help="Print diagnostic info.",
    action='count',
    default=0)
  parser.add_argument(
    '--no-hierarchy',
    help="Generate hierarchical plan (WBS).",
    dest='hierarchy',
    action='store_false',
    default=True)
  parser.add_argument(
    '--print-stack',
    help="Print call stack on error (INTERNAL).",
    action='store_true')
  parser.add_argument(
    '--dump',
    help="Print generated internal files to stdout (instead of passing them to external programs like Graphviz or TaskJuggler).",
    action='store_true')

  args = parser.parse_args()

  if args.iter is not None and args.action != 'burn':
    error("--iter/-i is only implemented for burndown charts")

  if args.bias is not None:
    try:
      bias = E.Bias[args.bias.upper().replace('-', '_')]
    except KeyError:
      error("unknown bias value '%s'" % v)
  else:
    bias = E.Bias.NONE
  estimator = E.RiskBasedEstimator(bias)

  set_options(print_stack=args.print_stack)

  if args.plan is None:
    filename = '<stdin>'
    f = sys.stdin
  else:
    filename = args.plan
    f = open(filename, 'r')

  parser = PA.Parser(args.v)
  parser.reset(filename, f)
  net, project, sched = parser.parse(args.W)

  if args.action in ['tj', 'msp'] and not project.members:
    error("--tj and --msp require member info in project file")

  net.check(args.W)

  if args.only is not None:
    roots = []
    for name in args.only.split(';'):
      goal = net.name_to_goal.get(name)
      error_if(goal is None, "goal '%s' not present in plan" % name)
      roots.append(goal)
    goals = set()
    G.visit_goals(roots, callback=lambda g: goals.add(g.name), succs=False)
    net.filter(goals, args.W)

  wbs = WBS.create_wbs(net, args.hierarchy, args.v)
  p = PR.SourcePrinter()

  if args.action == 'tj':
    tj.export(project, wbs, estimator, args.dump)
  elif args.action == 'pert':
    pert.export(net, args.dump)
  elif args.action == 'msp':
    msp.export(project, wbs, args.dump)
  elif args.action == 'dump':
    project.dump(p)
    net.dump(p)
    sched.dump(p)
  elif args.action == 'dump-wbs':
    wbs.dump(p)
  elif args.action == 'schedule':
    scheduler = S.Scheduler(estimator, args.v)
    timetable = scheduler.schedule(project, net, sched)
    timetable.dump(p)
  elif args.action in ('burn', 'burndown'):
    if args.iter is None:
      duration = project.duration
      goal = roots[0]
    else:
      goals = net.iter_to_goals.get(args.iter)
      error_if(goals is None, "iteration '%s' is not present in plan" % args.phase)

      # Start date is the minimum of start times for all goals in current iteration
      # or finish times of all goals in previous iterations.
      start_date = finish_date = None
      for g in goals:
        if g.start_date is not None:
          start_date = min(start_date or g.start_date, g.start_date)
        for pred in g.preds:
          if pred not in goals and g.finish_date is not None:
            start_date = min(start_date or pred.finish_date, pred.finish_date)
        if g.deadline is not None:
          finish_date = min(finish_date or g.deadline, g.deadline)
      error_if(start_date is None, "unable to determine start date for iteration '%s'" % args.iter)
      error_if(finish_date is None, "unable to determine finish date for deadline '%s'" % args.iter)
      duration = I.Interval(start_date, finish_date)

    burn.export(net, goal, duration, args.dump)

if __name__ == '__main__':
    main()
