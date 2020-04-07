#!/usr/bin/env python2.7

# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

# Poor man's converter for Gaperton's declarative plans.
# Run with --help for details.
#
# TODO (global):
# * effortless but assigned tasks cause TJ to abort
# * export to MSP (Project Elements and XML Structure: https://msdn.microsoft.com/en-us/library/bb968652%28v=office.12%29.aspx)
# * emit warnings (loops, etc.)
# * add internal docs
# * publish
# * minor TODOs scattered over codebase

import sys
import argparse

from gaplan.common.error import error, set_basename
from gaplan.common import error as E
from gaplan.common import ETA
from gaplan.common import printers as PR
from gaplan.goal import parse as PA
from gaplan.goal import goal as G

from gaplan.goal.export import pert
from gaplan.goal.export import tj
from gaplan.goal.export import msp
from gaplan.goal.export import burn

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

Examples:
  Pretty print a project:
  $ {exe} dump plan.txt

  Generate PERT diagram:
  $ {exe} pert plan.txt | dot -Tpdf > plan.pdf

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
    choices=['dump', 'tj', 'msp', 'pert', 'burn', 'burndown'])
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
    choices=['pessimist', 'optimist', 'none'],
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
    '--hierarchy',
    help="Generate hierarchical plan (WBS).",
    action='store_true',
    default=False)
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
    error("--iter/-i is only implemented for burndown charts right now")

  good_biases = ['none', 'pessimist', 'optimist']
  if args.bias not in good_biases:
    error("unknown bias: %s (supported biases are %s)"
          % (args.bias, ', '.join(good_biases)))
  ETA.set_options(estimate_bias=args.bias)

  if args.plan is None:
    filename = '<stdin>'
    f = sys.stdin
  else:
    filename = args.plan
    f = open(filename, 'r')

  project_info, roots = PA.parse_goals(filename, f)

  if args.action in ['tj', 'msp'] and not project_info.members:
    error("--tj and --msp require member info in project file")

  if args.action not in ['tj', 'msp'] and args.hierarchy:
    error("--hierarchy supported only for tj and msp actions")

  net = G.Net(project_info, roots, args.W)
  net.check(args.W)

  if args.only is not None:
    roots = []
    for name in args.only.split(';'):
      if name not in net.name_to_goal:
        error("goal '%s' not present in plan" % name)
      roots.append(net.name_to_goal[name])
    goals = set()
    G.visit_goals(roots, callback=lambda g: goals.add(g.name), succs=False)
    net.filter(goals, args.W)

  if args.action == 'tj':
    tj.export(net, args.hierarchy, args.dump)
  elif args.action == 'pert':
    pert.export(net, args.dump)
  elif args.action == 'msp':
    msp.export(net, args.hierarchy, args.dump)
  elif args.action == 'dump':
    net.dump(PR.SourcePrinter())
  elif args.action in ('burn', 'burndown'):
    if args.iter is None:
      start_date = net.project_info.start
      finish_date = net.project_info.finish
      goal = roots[0]
    else:
      if args.iter not in net.iter_to_goals:
        error("iteration '%s' is not present in plan" % args.phase)
      goals = net.iter_to_goals[args.iter]

      # Start date is the minimum of start times for all goals in current iteration
      # or finish times of all goals in previous iterations.
      start_date = finish_date = None
      for g in goals:
        if g.start_date is not None:
          start_date = g.start_date if start_date is None else min(start_date, g.start_date)
        for pred in g.preds:
          if pred not in goals and g.finish_date is not None:
            start_date = pred.finish_date if start_date is None else min(start_date, pred.finish_date)
        if g.deadline is not None:
          finish_date = g.deadline if finish_date is None else min(finish_date, g.deadline)
      if start_date is None:
        error("unable to determine start date for iteration '%s'" % args.iter)
      if finish_date is None:
        error("unable to determine finish date for deadline '%s'" % args.iter)

    burn.export(net, goal, start_date, finish_date, args.dump)

if __name__ == '__main__':
    main()
