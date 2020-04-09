# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
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
from gaplan.common import platform

time_format = '%Y-%m-%d'

def _print_alloc(p, names, full_parallel):
  if full_parallel:
    for n in names:
      p.writeln('allocate %s' % n)
  else:
    names = list(names)
    first = names[0]
    rest = names[1:]
    alts = ('alternative ' + ', '.join(rest)) if rest else ''
    p.writeln('allocate %s { %s select minloaded persistent}' % (first, alts))

def _tj_prio(goal):
  prio = goal.priority()
  return None if prio is None else int(prio * 1000)

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

def _is_goal_ignored(g):
  return g.dummy and not g.preds

# Do not print empty dummy activities
def _is_activity_ignored(act):
  return act.head is not None \
    and not act.effort.defined() \
    and _is_goal_ignored(act.head)

def _print_activity_body(p, act, abs_ids, complete, teams, tracker_link, pr_link):
  _print_jira_links(p, act.jira_tasks, act.pull_requests, tracker_link, pr_link)

  effort = _tj_effort(act)

  # TODO: move this to project info
  resources = set()
  for a in (['all'] if not act.alloc else act.alloc):
    team = teams.get(a)
    if team is not None:
      resources.update(m.name for m in team.members)
    else:
      resources.add(a)

  if effort > 0 and act.parallel:
    # Split activity to several tasks for parallelism
    num_tasks = min(act.parallel, len(resources))
    has_sub_tasks = True
  else:
    num_tasks = 1
    has_sub_tasks = False

  for t in range(num_tasks):
    if has_sub_tasks:
      p.writeln('task id%d "" {' % t)

    p.writeln('scheduling asap')

    if effort > 0:
      task_effort = float(effort) / num_tasks
      if complete == 100:
        p.writeln('complete %d' % complete)
      else:
        task_effort = task_effort * (1 - complete / 100.0)
#        p.writeln('complete %d' % complete)
        p.writeln('depends now')

      p.writeln('effort %dh' % round(task_effort))

      # We print allocated resources only if effort > 0
      # (TJ aborts otherwise)
      _print_alloc(p, resources, False)  # act.is_max_parallel()

    if act.is_scheduled():
      p.writeln('start %s' % PR.print_date(act.start_date))
      p.writeln('end %s' % PR.print_date(act.finish_date))
      p.writeln('scheduled')
      # Can't specify dependencies for fixed tasks
      # due to "XXX must start after end of YYY".
    elif not _is_activity_ignored(act):
      p.writeln('depends %s' % abs_ids[act.head.name])

    if has_sub_tasks:
      p.writeln('}')

def _massage_name(name):
  return re.sub(r'"', '\\"', name)

def _print_activity(p, act, id, abs_ids, name, complete, teams,
                    tracker_link, pr_link):
  p.writeln('task %s "%s" {' % (id, _massage_name(name)))
  with p:
    _print_activity_body(p, act, abs_ids, complete, teams, tracker_link,
                         pr_link)
  p.writeln('}')

def _print_jira_links(p, tasks, pull_requests, tracker_link, pr_link):
  for t in tasks:
    p.writeln(('JiraLink "' + tracker_link + '" {label "#%s"}') % (t, t))
    break
  else:
    for pr in pull_requests:
      p.writeln(('JiraLink "' + pr_link + '" {label "PR #%s"}') % (pr, pr))
      break

def _print_goal(p, goal, ids, abs_ids, teams, tracker_link, pr_link):
  id = ids[goal.name]
  abs_id = abs_ids[goal.name]

  complete = goal.complete()

  p.writeln('task %s "%s" {' % (id, _massage_name(goal.name)))
  p.enter()

  for act in goal.global_preds:
    if act.head:
      p.writeln('depends %s' % abs_ids[act.head.name])

  if goal.is_instant():
    p.writeln('milestone')

  prio = _tj_prio(goal)
  if prio is not None:
    p.writeln('priority %d' % prio)

  if goal.is_scheduled():
    if goal.preds:
      error_loc(goal.loc, "TJ can't schedule non-milestone goal '%s'" % goal.name)
    d = PR.print_date(goal.completion_date)
    p.writeln('start %s' % d)
    p.writeln('end %s' % d)
    p.writeln('scheduled')
  elif goal.has_single_activity():
    # Translate atomic goals to atomic TJ tasks
    _print_activity_body(p, goal.preds[0], abs_ids, complete, teams,
                         tracker_link, pr_link)
  else:
    # First print dependencies
    for act in (a for a in goal.preds if a.is_instant()):
      if act.is_instant():
        p.writeln('depends %s' % abs_ids[act.head.name])
    for i, act in enumerate(a for a in goal.preds \
                            if not a.is_instant() and not _is_activity_ignored(a)):
      _print_activity(p, act, '%s_%d' % (id, i), abs_ids, 'Task %d' % i,
                      complete, teams, tracker_link, pr_link)

  p.exit()
  p.writeln('}')

  if goal.deadline is not None:
    p.writeln('task %s_deadline "%s (deadline)" {' % (id, _massage_name(goal.name)))
    p.write('  scheduling asap')
    p.write('  depends %s' % abs_id)
    #p.write('%s  start %s' % goal.deadline.strftime(time_format))
    p.write('  maxstart %s' % goal.deadline.strftime(time_format))
    p.write('}')

def _print_goal_hierarchical(p, goal, ids, abs_ids, children, teams,
                             tracker_link, pr_link):
  id = ids[goal.name]
  abs_id = abs_ids[goal.name]

  complete = goal.complete()

  p.writeln('task %s "%s" {' % (id, _massage_name(goal.name)))
  p.enter()

  for act in goal.global_preds:
    if act.head:
      p.writeln('depends %s' % abs_ids[act.head.name])

#  TODO
#  if goal.is_instant():
#    p.writeln('milestone')

  prio = _tj_prio(goal)
  if prio is not None:
    p.writeln('priority %d' % prio)

  def is_child(g):
    return g is None or g.name in children[goal.name]

  if goal.is_scheduled():
    if goal.preds:
      error_loc(goal.loc, "TJ can't schedule non-milestone goal '%s'" % goal.name)
    d = PR.print_date(goal.completion_date)
    p.writeln('start %s' % d)
    p.writeln('end %s' % d)
    p.writeln('scheduled')
  else:
    # First print instant dependencies
    for act in (a for a in goal.preds
                if a.is_instant() and not is_child(a.head)):
      p.writeln('depends %s' % abs_ids[act.head.name])

    # Then print goal-specific tasks
    for i, act in enumerate(a for a in goal.preds
                            if not a.is_instant() and not _is_activity_ignored(a)):
      _print_activity(p, act, '%s_%d' % (id, i), abs_ids, 'Task %d' % i,
                      complete, teams, tracker_link, pr_link)

  for g in goal.children:
    _print_goal_hierarchical(p, g, ids, abs_ids, children, teams, tracker_link, pr_link)

  p.exit()
  p.writeln('}')

  if goal.deadline is not None:
    p.writeln('task %s_deadline "%s (deadline)" {' % (id, _massage_name(goal.name)))
    p.write('  scheduling asap')
    p.write('  depends %s' % abs_id)
    #p.write('%s  start %s' % goal.deadline.strftime(time_format))
    p.write('  maxstart %s' % goal.deadline.strftime(time_format))
    p.write('}')

def _print_iterative(net, p, ids, teams):
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
      if not _is_goal_ignored(g):
        with p:
          _print_goal(p, g, ids, abs_ids, teams,
                      net.project.tracker_link,
                      net.project.pr_link)

    p.writeln('}\n')

def _print_hierarchical(net, p, ids, teams):
  children = {}
  def cache_children(g):
    children[g.name] = set()
    for child in g.children:
      children[g.name].add(child.name)
      children[g.name].update(children[child.name])
  net.visit_goals(after=cache_children, hierarchical=True)

  abs_ids = {}
  def cache_abs_id(g):
    if g.parent is None:
      abs_ids[g.name] = ids[g.name]
    else:
      abs_ids[g.name] = '%s.%s' % (abs_ids[g.parent.name], ids[g.name])
  net.visit_goals(callback=cache_abs_id, hierarchical=True)

  for g in net.roots:
    if not _is_goal_ignored(g):
      with p:
        _print_goal_hierarchical(p, g, ids, abs_ids, children,
                                 teams, net.project.tracker_link,
                                 net.project.pr_link)

def export(net, hierarchy, dump=False):
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
    reference JiraLink "Tracker link"
  }}
}}

flags internal

'''.format(project_name=net.project.name,
           start=PR.print_date(net.project.start),
           finish=PR.print_date(net.project.finish),
           time_format=time_format,
           now=today.strftime(time_format)))

  # TODO: additional holidays in project info?
  for y in range(net.project.start.year, net.project.finish.year + 1):
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
  for dev in net.project.members:
    p.writeln('  resource %s "%s" {' % (dev.name, dev.name))
    p.writeln('    efficiency %f' % dev.efficiency)
    for start, finish in dev.vacations:
      p.writeln('    vacation %s - %s'
                % (start.strftime(time_format), finish.strftime(time_format)))
    p.writeln('  }')
  p.writeln('}')

  if hierarchy:
    _print_hierarchical(net, p, ids, net.project.teams_map)
  else:
    _print_iterative(net, p, ids, net.project.teams_map)

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
  timeformat "%Y-%m-%d"
  formats html
  columns bsi {{ title 'ID' }}, name, JiraLink, start, end, effort, resources, chart {{ width 5000 }}
  loadunit weeks
  sorttasks tree
  hidetask (internal)
}}

resourcereport resources "ResourceGraph" {{
  headline "{project_name} - Resource Allocation Report"
  timeformat "%Y-%m-%d"
  formats html
  columns bsi, name, JiraLink, start, end, effort, chart {{ width 5000 }}
#  loadunit weeks
  sorttasks tree
  hidetask (internal | ~isleaf_())
  hideresource ~isleaf()
}}

tracereport trace "TraceReport" {{
  columns bsi, name, start, end
  timeformat "%Y-%m-%d"
  formats csv
}}

export msproject "{project_name}" {{
  formats mspxml
}}
'''.format(project_name=net.project.name))

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
