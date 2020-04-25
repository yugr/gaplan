# The MIT License (MIT)
# 
# Copyright (c) 2016-2020 Yury Gribov
# 
# Use of this source code is governed by The MIT License (MIT)
# that can be found in the LICENSE.txt file.

# THIS IS NYI

import datetime
import io

from gaplan.common import printers as P
from gaplan.common.error import error, error_loc

time_format = '%Y-%m-%d'

def _prio(g):
  # TODO: take risk into account
  return int(g.priority() * 1000)

def _print_date(d):
  return d.strftime(time_format) + 'T00:00:00'

def _print_activity_body(a, uids, out):
  print('''\
      <IsNull>0</IsNull>
''', file=out)

  if a.duration.start is not None:
    assert a.duration.finish is not None
    s = _print_date(a.duration.start)
    f = _print_date(a.duration.finish)
    # "Must start on"
    print('''\
      <ConstraintType>2</ConstraintType>
      <ConstraintDate>%s</ConstraintDate>
      <Start>%s</Start>
      <Finish>%s</Finish>
      <ManualStart>%s</ManualStart>
      <ManualFinish>%s</ManualFinish>
      <ActualStart>%s</ActualStart>
      <ActualFinish>%s</ActualFinish>
''' % (s, s, f, s, f, s, f), file=out)
  else:
    # "As soon as possible"
    print('''\
      <ConstraintType>0</ConstraintType>
''', file=out)

  # Fixed work
  print('''\
      <Type>2</Type>
''', file=out)

  # TODO: dependencies, completeness

def _print_activity(a, name, uids, out):
  uid = uids[a]
  print('''\
    <Task>
      <UID>%d</UID>
      <ID>%d</ID>
      <Name>%s</Name>
      <IsNull>0</IsNull>
''' % (uid, uid,), file=out)

  # TODO

  print('''\
    </Task>
''', file=out)

def _print_goal(g, uids, ids, out):
  uid = uids[g]

#  num_acts = len(goal.preds)
#  complete = goal.complete()

  print('''\
    <Task>
      <UID>%d</UID>
      <ID>%d</ID>
      <Name>%s</Name>
      <IsNull>0</IsNull>
''' % (uid, uid, g.name), file=out)

  print('''\
      <Priority>%d</Priority>
''' % _prio(g), file=out)

  if g.deadline is not None:
    # "Finish no later than"
    d = _print_date(g.deadline)
    print('''\
      <ConstraintType>7</ConstraintType>
      <ConstraintDate>%s</ConstraintDate>
      <Deadline>%s</Deadline>
''' % (d, d), file=out)

  if g.is_leaf():
    # We can merge activity and goal
    _print_activity_body(g.preds[0], uids, out)
    print('''\
    </Task>
''', file=out)
    return

  # Else print task per activity
  # TODO: dependencies
  print('''\
      <Milestone>1</Milestone>
    </Task>
''', file=out)

  i = 1
  for act in g.preds:
   if not act.is_instant():
     _print_activity(act, '%s (%d)' % (g.name, i), uids, out)
     i += 1

  # TODO:
  # Predecessor
  # Resources
  # Effort
  # Duration
  # <WBS>2.3.3.4.4</WBS>
  # WBSLevel
  # <OutlineNumber>2.3.3.4.4</OutlineNumber>
  # <OutlineLevel>4</OutlineLevel>
  # <Priority>500</Priority>
  # <PercentComplete>100</PercentComplete>
  # <PercentWorkComplete>100</PercentWorkComplete>
  # Contact

def export(project, net, hierarchy, dump=False):
#  today = datetime.date.today()

  next_uid = [0]  # Python's craziness
  uids = {}
  def assign_uid(g):
    if g in uids:
      return

    uids[g] = next_uid[0]
    next_uid[0] += 1

    if g.is_leaf():
      return

    for a in g.preds:
      if not a.is_instant():
        uids[a] = next_uid[0]
        next_uid[0] += 1

  net.visit_goals(callback=assign_uid)

  out = io.StringIO()

  # Based upon "Introduction to Project XML Data": https://msdn.microsoft.com/en-us/library/bb968652%28v=office.12%29.aspx
  print('''\
<Project xmlns="http://schemas.microsoft.com/project">
  <Name>%s</Name>
  <StartDate>%s</StartDate>
  <FinishDate>%s</FinishDate>
  <DefaultStartTime>09:00:00</DefaultStartTime>
  <DefaultFinishTime>17:00:00</DefaultFinishTime>
  <SpreadPercentComplete>0</SpreadPercentComplete>

  <Tasks>
''' % (net.project.name, P.print_date(net.project.start), P.print_date(net.project.finish)), file=out)

  # TODO
  net.visit_goals(callback=lambda g: _print_goal(g, uids, ids, out))

  print('''\
  </Tasks>
</Project>
''', file=out)

  if dump:
    print(out.getvalue())
  else:
    xml_file = 'plan.xml'

    f = open(xml_file, 'w')
    f.write(out.getvalue())
    f.close()
