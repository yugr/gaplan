# The MIT License (MIT)
# 
# Copyright (c) 2016-2018 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

import datetime
import io
import os
import os.path
import subprocess
import re

from gaplan.common.error import error, error_loc
from gaplan.common import printers as PR

time_format = '%Y-%m-%d'

def _print_alloc(p, names, parallel):
  if parallel:
    for n in names:
      p.writeln('allocate %s' % n)
  else:
    first = names[0]
    rest = names[1:]
    alts = ('alternative ' + ', '.join(rest)) if rest else ''
    p.writeln('allocate %s { %s select minloaded persistent}' % (first, alts))

def _tj_prio(goal):
  # TODO: take risk into account
  return int(goal.priority() * 1000)

def _tj_effort(act):
  eta = act.effort.real
  if eta is None:
    eta, _ = act.effort.estimate(act.tail.risk if act.tail else None)
  if eta is None:
    eta = 0
  return eta

# We should not issue "depends" marker if task is already child
# (because TJ will abort)
def _needs_explicit_depends(act):
  g = act.tail
  return act.head is not None and act.head not in g.children

def _print_activity_body(p, act, abs_ids, complete, all_alloc):
  _print_jira_links(p, act.jira_tasks)

  p.writeln('scheduling asap')

  effort = _tj_effort(act)
  if effort > 0:
    if complete == 100:
      p.writeln('complete %d' % complete)
    else:
      effort = effort * (1 - complete / 100.0)
#      p.writeln('complete %d' % complete)
      p.writeln('depends now')

    p.writeln('effort %dh' % int(effort))

    # We print allocated resources only if effort > 0
    # (TJ aborts otherwise)
    alloc = act.alloc if act.alloc else all_alloc
    _print_alloc(p, alloc, act.parallel)

  if act.is_scheduled():
    p.writeln('start %s' % PR.print_date(act.start_date))
    p.writeln('end %s' % PR.print_date(act.finish_date))
    p.writeln('scheduled')
    # Can't specify dependencies for fixed tasks
    # due to "XXX must start after end of YYY".
  elif act.head is not None:
    p.writeln('depends %s' % abs_ids[act.head.name])

def _massage_name(name):
  return re.sub(r'"', '\\"', name)

def _print_activity(p, act, id, abs_ids, name, complete, all_alloc):
  p.writeln('task %s "%s" {' % (id, _massage_name(name)))
  with p as p:
    _print_activity_body(p, act, abs_ids, complete, all_alloc)
  p.writeln('}')

def _print_jira_links(p, tasks):
  for t in tasks:
    # TODO: path from project info
    p.writeln('JiraLink "http://jira.localhost/browse/%s" {label "%s"}' % (t, t))
    break

def _print_goal(p, goal, ids, abs_ids, all_alloc):
  id = ids[goal.name]
  abs_id = abs_ids[goal.name]

  complete = goal.complete()

  p.writeln('task %s "%s" {' % (id, _massage_name(goal.name)))
  p.enter()

  for act in goal.global_preds:
    if act.head:
      p.writeln('depends %s' % abs_ids[act.head.name])

  if goal.is_milestone():
    p.writeln('milestone')

  if goal.is_scheduled():
    if goal.preds:
      error_loc(goal.loc, 'TJ can''t schedule non-milestone goal "%s"' % goal.name)
    d = PR.print_date(goal.completion_date)
    p.writeln('start %s' % d)
    p.writeln('end %s' % d)
    p.writeln('scheduled')
  elif goal.is_atomic():
    # Translate atomic goals to atomic TJ tasks
    _print_activity_body(p, goal.preds[0], abs_ids, complete, all_alloc)
  else:
    i = 1
    for act in goal.preds:
      if act.is_instant():
        p.writeln('depends %s' % abs_ids[act.head.name])
      else:
        _print_activity(p, act, '%s_%d' % (id, i), abs_ids, 'Task %d' % i, complete, all_alloc)
        i += 1

  p.exit()
  p.writeln('}')

  if goal.deadline is not None:
    p.writeln('task %s_deadline "%s (deadline)" {' % (id, _massage_name(goal.name)))
    p.write('  scheduling asap')
    p.write('  depends %s' % abs_id)
    #p.write('%s  start %s' % goal.deadline.strftime(time_format))
    p.write('  maxstart %s' % goal.deadline.strftime(time_format))
    p.write('}')

def export(net, dump=False):
  today = datetime.date.today()

  next_id = [0]  # Python's craziness
  ids = {}
  def assign_id(g):
    if g.name not in ids:
      if g.alias is not None:
        ids[g.name] = g.alias
      else:
        ids[g.name] = 'id_%d' % next_id[0]
        next_id[0] += 1

  net.visit_goals(callback=assign_id)

  p = PR.SourcePrinter(io.StringIO())

  # Based upon http://www.taskjuggler.org/tj3/manual/Tutorial.html
  p.write('''\
project "{project_name}" {start} - {finish} {{
  timeformat "{time_format}"
  now {now}
  timezone "Europe/Moscow"
  currency "USD"
  extend task {{
    reference JiraLink "JIRA link"
  }}
}}

flags internal

'''.format(project_name=net.project_info['name'],
           start=PR.print_date(net.project_info['start']),
           finish=PR.print_date(net.project_info['finish']),
           time_format=time_format,
           now=today.strftime(time_format)))

  # TODO: years and holidays should be in project file
  for y in range(2015, 2020):
    for name, dates in [
        ('New year holidays', '01-01 + 8d'),
        ('Army day',          '02-23'),
        ('Womens day',        '03-08'),
        ('May holidays',      '05-01 + 2d'),
        ('Victory day',       '05-09'),
        ('Independence day',  '06-12'),
        ('Unity day',         '11-04')]:
      p.writeln('leaves holiday "%s %d" %d-%s' % (name, y, y, dates))
  p.writeln('')

  p.writeln('resource dev "Developers" {')
  for dev in net.project_info['members']:
    p.writeln('  resource %s "%s" {' % (dev.name, dev.name))
    p.writeln('    efficiency %f' % dev.eff)
# TODO: enable leaves
#    leaves = data['leaves']
#    if leaves:
#      p.writeln('    leaves annual ' + ', annual '.join(leaves))
    p.writeln('  }')
  p.writeln('}')

  all_alloc = list(map(lambda m: m.name, net.project_info['members']))

  user_iters = list(filter(lambda i: i is not None, net.iter_to_goals.keys()))
  user_iters.sort()
  last_iter = (user_iters[-1] + 1) if user_iters else 0

  abs_ids = {}
  def cache_abs_id(g):
    abs_ids[g.name] = 'iter_%d.%s' % (last_iter if g.iter is None else g.iter, ids[g.name])

  net.visit_goals(callback=cache_abs_id)

  for i in user_iters + [None]:
    i_num = last_iter if i is None else i

    p.write('''\
task iter_%d "Iteration %d" {
''' % (i_num, i_num))

    if i_num > 0:
      p.writeln('  depends iter_%d' % (i_num - 1))

    for g in net.iter_to_goals[i]:
      with p as p:
        _print_goal(p, g, ids, abs_ids, all_alloc)

    p.writeln('}\n')

  # A hack to prevent TJ from scheduling unfinished tasks in the past
  p.write('''\
task now "Now" {
  milestone
  flags internal
  start ${now}
}

''')

  p.write('''\
taskreport gantt "GanttChart" {{
  headline "{project_name} - Gantt Chart"
  timeformat "%%Y-%%m-%%d"
  formats html
  columns bsi {{ title 'ID' }}, name, JiraLink, start, end, effort, resources, chart {{ width 5000 }}
  loadunit weeks
  sorttasks tree
  hidetask (internal)
}}

resourcereport resources "ResourceGraph" {{
  headline "{project_name} - Resource Allocation Report"
  timeformat "%%Y-%%m-%%d"
  formats html
  columns bsi, name, JiraLink, start, end, effort, chart {{ width 5000 }}
#  loadunit weeks
  sorttasks tree
  hidetask (internal | ~isleaf_())
  hideresource ~isleaf()
}}

tracereport trace "TraceReport" {{
  columns bsi, name, start, end
  timeformat "%%Y-%%m-%%d"
  formats csv
}}

export msproject "{project_name}" {{
  formats mspxml
}}
'''.format(project_name=net.project_info['name']))

  if dump:
    print(p.out.getvalue())
  else:
    tjp_file = 'plan.tjp'
    tj_dir = './tj'

    with open(tjp_file, 'w') as f:
      f.write(p.out.getvalue())

    if not os.path.exists(tj_dir):
      os.mkdir(tj_dir)

    if 0 != subprocess.call(['tj3', '-o', tj_dir, tjp_file]):
      error("failed to run tj3; do you have TaskJuggler installed?")

    platform.open_file(os.path.join(tj_dir, 'GanttChart.html'))
    platform.open_file(os.path.join(tj_dir, 'ResourceGraph.html'))
