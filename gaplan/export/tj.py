# The MIT License (MIT)
# 
# Copyright (c) 2018-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

"""TaskJuggler exporter for declarative plans."""

import datetime
import io
import os
import os.path
import subprocess
import re

from gaplan.common.error import error
import gaplan.common.printers as PR
from gaplan.common import platform
import gaplan.goal as G

time_format = '%Y-%m-%d'

def _escape(name):
  return re.sub(r'"', '\\"', name)

def _print_jira_links(p, tracker, prj):
  for t in tracker.tasks:
    p.writeln(f'JiraLink "{prj.tracker_link}" {{label "#{t}"}}')
    break
  else:
    for pr in tracker.prs:
      p.writeln(f'JiraLink "{prj.pr_link}" {{label "PR #{pr}"}}')
      break

def _print_task(p, task, abs_ids, prj, est):
  abs_id = abs_ids[task.id]

  escaped_name = _escape(task.name)
  p.writeln(f'task {task.id} "{escaped_name}" {{')
  p.enter()

  p.writeln('scheduling asap')

  if task.prio is not None:
    # TODO: also task risk into account
    prio = int(1000 * G.Priority.rel(task.prio))
    p.writeln(f'priority {prio}')

  if not task.subtasks and not task.activities and not task.act:
    p.writeln('milestone')

  for dep in task.depends:
    p.writeln(f'depends {abs_ids[dep]}')

  act = task.act
  if act is not None:
    _print_jira_links(p, act.tracker, prj)

    effort = act.effort.real
    # TODO: act.effort.completion
    if effort is None:
      effort, _ = est.estimate(act)
    if effort is None:
      effort = 0

    resources = prj.get_resources(act.alloc)

    # TODO: handle act.parallel (in WBS)
    # TODO: handle act.overalap
    if effort > 0:
      task_effort = float(effort)

      if task.complete is not None:
        if task.complete == 100:
          p.writeln(f'complete {task.complete}')
        else:
          task_effort = task_effort * (1 - task.complete / 100.0)
#          p.writeln('complete %d' % task.complete)
          p.writeln('depends now')
      else:
        p.writeln('depends now')

      p.writeln(f'effort {round(task_effort)}h')

      # We print allocated resources only if effort > 0
      # (TJ aborts otherwise)
      if act.is_max_parallel():
        for rc in resources:
          p.writeln(f'allocate {rc.name}')
      else:
        first = resources[0].name
        rest = list(map(lambda rc: rc.name, resources[1:]))
        alts = ('alternative ' + ', '.join(rest)) if rest else ''
        p.writeln(f'allocate {first} {{ {alts} select minloaded persistent }}')

  if task.duration is not None:
    p.writeln(f'start {act.duration.start}')
    p.writeln(f'end {act.duration.finish}')
    p.writeln('scheduled')

  for subtask in (task.activities + task.milestones):
    _print_task(p, subtask, abs_ids, prj, est)

  for child in task.subtasks:
    _print_task(p, child, abs_ids, prj, est)

  p.exit()
  p.writeln('}')

  if task.deadline is not None:
    escaped_name = _escape(task.name)
    p.writeln(f'task {task.id}_deadline "{escaped_name} (deadline)" {{')
    p.write('  scheduling asap')
    p.write('  milestone')
    p.write(f'  depends {abs_id}')
    #p.write('%s  start %s' % task.deadline.strftime(time_format))
    p.write('  maxstart ' + task.deadline.strftime(time_format))
    p.write('}')

def export(prj, wbs, est, dump=False):
  """Generate TaskJuggler plan from declarative plan."""

  today = datetime.date.today()

  p = PR.SourcePrinter(io.StringIO())

  # Print header
  # (based upon http://www.taskjuggler.org/tj3/manual/Tutorial.html)

  p.write(f'''\
project "{prj.name}" {prj.start} - {prj.finish} {{
  timeformat "{time_format}"
  now {today.strftime(time_format)}
  timezone "Europe/Moscow"
  currency "USD"
  extend task {{
    reference JiraLink "Tracker link"
  }}
}}

flags internal

''')

  # Print holidays
  # TODO: additional holidays in plan

  for y in range(prj.start.year, prj.finish.year + 1):
    for name, dates in [
        ('New year holidays', '01-01 + 8d'),
        ('Army day',          '02-23'),
        ('Womens day',        '03-08'),
        ('May holidays',      '05-01 + 2d'),
        ('Victory day',       '05-09'),
        ('Independence day',  '06-12'),
        ('Unity day',         '11-04')]:
      p.writeln(f'leaves holiday "{name} {y}" {y}-{dates}')
  p.writeln('')

  # Print resources

  p.writeln('resource dev "Developers" {')
  for dev in prj.members:
    p.writeln(f'  resource {dev.name} "{dev.name}" {{')
    p.writeln(f'    efficiency {dev.efficiency}')
    for iv in dev.vacations:
      p.writeln(f'    vacation {iv.start} - {iv.finish}')
    p.writeln('  }')
  p.writeln('}')

  # Print WBS

  abs_ids = {}
  def cache_abs_id(task):
    if task.parent is None:
      abs_ids[task.id] = task.id
    else:
      parent_id = abs_ids[task.parent.id]
      abs_ids[task.id] = f'{parent_id}.{task.id}'
  wbs.visit_tasks(cache_abs_id)

  for task in wbs.tasks:
    _print_task(p, task, abs_ids, prj, est)

  # A hack to prevent TJ from scheduling unfinished tasks in the past
  p.write('''\
task now "Now" {
  milestone
  flags internal
  start ${now}
}

''')

  # Print reports

  p.write(f'''\
taskreport gantt "GanttChart" {{
  headline "{prj.name} - Gantt Chart"
  timeformat "%Y-%m-%d"
  formats html
  columns bsi {{ title 'ID' }}, name, JiraLink, start, end, effort, resources, chart {{ width 5000 }}
  loadunit weeks
  sorttasks tree
  hidetask (internal)
}}

resourcereport resources "ResourceGraph" {{
  headline "{prj.name} - Resource Allocation Report"
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

export msproject "{prj.name}" {{
  formats mspxml
}}
''')

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
