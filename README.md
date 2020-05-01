[![License](http://img.shields.io/:license-MIT-blue.svg)](https://github.com/yugr/gaplan/blob/master/LICENSE.txt)
[![Total alerts](https://img.shields.io/lgtm/alerts/g/yugr/gaplan.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/yugr/gaplan/alerts/)

# What is this?

Gaplan is a simple but functional toolset for constructing and
analyzing [Gaperton's](http://gaperton.livejournal.com)
(aka Vlad Balin's) *declarative plans*.

It supports plan analysis (mainly checking for common mistakes)
and generation of various artifacts (e.g PERT diagrams,
[TaskJuggler](http://taskjuggler.org/) plans and burndown charts).

This is very much a work-in-progress, driven by my own planning needs.
I'm happy to improve the tool so ping me if you consider using it.

# About declarative planning

Declarative planning is a goal-based approach to building plans,
backed up with an easy-to-use notation for writing them down.

Declarative plannig can be roughly described as modelling projects
via [PERT](https://en.wikipedia.org/wiki/Program_evaluation_and_review_technique)-like
[activity-on-edges](https://en.wikipedia.org/wiki/Arrow_diagramming_method) diagrams
with focus on well-defined *events* (called *goals*) rather than activities.
Goals are defined through their accomplishment criteria.
Declarative plans are often called *goal maps* (probably to pun on
Alistair Cockburn's *project maps*) or [project networks](https://en.wikipedia.org/wiki/Project_network).

Declarative plans are
* easy to construct and verify (compared to traditional activity-based plans)
* scalable (can be written or collapsed to desired level of detail)
* stable against (inevitable) business and technical risks (e.g. changes in requirements or architecture)

For more information on declarative planning see
[Vlad's presentation on SoftwarePeople 2009](http://www.slideshare.net/gaperton/auftragsplanning-pre-final-1479467)
or his numerous blogposts (sadly all in Russian):
* [Как составлять планы, или "декларативное планирование"](http://gaperton.livejournal.com/16087.html)
* [Инструмент планирования - notepad](http://gaperton.livejournal.com/56976.html)
* [Инструмент планирования - notepad (2)](http://gaperton.livejournal.com/57204.html)
* [Аннотация к моему докладу на SoftwarePeople](http://gaperton.livejournal.com/32051.html)
* [Комментарий к "декларативному планированию"](http://gaperton.livejournal.com/32427.html)

# Install

`gaplan` is based on `setuptools` so to install simply run
```
$ python3 -mpip install .
```
in `gaplan`'s folder.

For tooltips in TaskJuggler download [wz_tooltip.js](http://www.walterzorn.de/en/tooltip/tooltip_e.htm)
to `scripts/` subfolder (note that it's distributed under LGPL).

# How to use

To use the toolset you first need to write
a [declarative plan](http://gaperton.livejournal.com/56976.html).
Take a look at example plans in `exampes/` folder (e.g. toolchain plan).

Now to build a PERT chart, do
```
# Requires Graphviz dot.exe in PATH
$ python3 -mgaplan pert plan.txt
```

To generate TaskJuggler project:
```
# Requires TaskJuggler in PATH
$ python3 -mgaplan tj plan.txt
```

To generate a burndown chart:
```
$ python3 -mgaplan burn --phase 'Iteration 1 completed' burndown plan.txt
```

To display generated files (instead of passing it to Graphviz or TaskJuggler) use `--dump` flag e.g.
```
$ python3 -mgaplan --dump pert plan.txt > plan.gv
$ dot -Tpdf < plan.gv > plan.pdf
```
or
```
$ python3 -mgaplan --dump tj plan.txt > plan.tjp
$ mkdir -p tjdir
$ tj3 plan.tjp -o tjdir
```

For additional details run
```
$ python3 -mgaplan --help
```

# Notation

The core of the syntax is Vlad's text notation for graphs:
```
|Ready for NY celebration
|<-
   |Bought food
   |[X] Bread
   |[] Cheese
   |<-
      |Bought alcohol  // !3
      |[] Wine
      |[] Alcohol
|<-  // @me, 1h-2h
   |Invited friends  // !3
   |[] Alex
   |[] Max
```

Example above illustrates few core concepts:
* only goals have names (`Invited friends`), priorities (`!3`) and internal structure (checklists)
* only activities (arrows) have duration (`1h-2h`) and assignees (`@me`)
See more examples in `examples/` subfoler.

Canonical notation has been extended with additional features which turned out to be useful in practice:
* Tool tries to infer hierarchical connections between tasks (i.e. [WBS](https://en.wikipedia.org/wiki/Work_breakdown_structure)) as they allow to produce more readable plans for TaskJuggler.
```
# A hierarchy of 3 nested goals
|Quality requirements fullfilled
|<-
   |Results of regression testing acceptable for beta
   |[] Regression testing logs ready
   |[] Number of regressions against prev. version <= 1%
   |[] All regressions against prev. version fixed or explained
   |<-
      |Results of regression testing acceptable for alpha
      |[] Regression testing logs ready
      |[] Number of regressions against prev. version <= 5%
```
* Goals can be annotated with various attributes (priority, risk, assignees, etc.) e.g.
```
# This goal has to be reached by the end of November, has max risk and priority and has to be scheduled in first iteration
|Symbol visibility in TZ 3.0 reduced  // deadline 2016-11-30, !3, ?3, I0
```
* In addition to normal dependencies (`|<-`, `|->`) tools supports _global dependencies_ (marked with `global`). Globality causes all hierarchical children of a goal to depend on RHS. It's useful for splitting plan into disjoint phases, where task in depending phase can not start until their global dependency completes. This is an experimental feature.
* Some goals many be unnamed (the so called "dummy PERT goals"):
```
|Feature X added
|<-  // 2d-1w
   |      # Unnamed ("dummy") goal
   |<-
      |Prerequisite 1
   |<-
      |Prerequisite 2
```

# Attributes

Goals can be annotated with special *attributes* listed in table below.

| Attribute           | Syntax                | Example               | Comments     |
|---------------------|:---------------------:|:---------------------:|:------------:|
| Priority            | !*PRIO*               | `!3`                  |              |
| Risk                | ?*RISK*               | `?3`                  |              |
| Deadline            | deadline *YYYY-MM-DD* | `deadline 2016-09-30` |              |
| Iteration           | I*NUMBER*             | `I2`                  |              |
| Accomplishment date | *YYYY-MM-DD*          | `2016-08-31`          |              |
| Alias               | alias *NAME*          | `alias mod2_test`     | Short name   |

3-stage scale is used for priorities:

| Prio | Description                                               |
|------|-----------------------------------------------------------|
| 1    | Default                                                   |
| 2    | Desirable but not required for project completion         |
| 3    | Project requirement (probably stated in project proposal) |

and for risks:

| Risk | Description                                                                    |
|------|--------------------------------------------------------------------------------|
| 1    | Know-how, have done similar stuff before                                       |
| 2    | No prior experience but known to be doable (e.g. already done by someone else) |
| 3    | No prior experience, not clear whether doable at all                           |

For example this statement
```
|Compiler rebuilds full distro  // deadline 2016-09-01, !3, ?1
...
```
says that the goal "Compiler rebuilds full distro" must be
completed by September (`deadline` attribute), is high-prio (`!3`)
and low-risk (`?1`).

There is a distinct set of attributes for activities:

| Attribute          | Syntax                    | Example                    | Comment                                            |
|--------------------|:-------------------------:|:--------------------------:|----------------------------------------------------|
| Effort estimate    | *min*-*max*                 | `1h-3d`, `1w-1m`                   | Activity effort estimate (in ["ideal hours"](http://www.martinfowler.com/bliki/IdealTime.html)) |
| Real effort        | *min*-*max* (*real*)        | `1h-3d (1d)`, `1w-1m (2w)`         | Real observed effort (used for tracking) |
| Real duration      | *YYYY-MM-DD*-*YYYY-MM-DD*   | `2016-05-31-2016-06-02`            | Real observed duration (used for tracking) |
| Assignees          | @*dev1*/*dev2*/...          | `@yura/slava`                      | Developers assigned to the task |
| Real Assignees     | @*dev1*/*dev2*/... (*real*) | `@yura/slava` (max)                | Developers who actually accomplished the task |
| Parallel impl.     | \|\|                        | \|\|                               | Notes that developers can work on task in parallel |
| Identifier         | id *symbolic\_name*         | id enable-jenkins-job              | Gives symbolic name to activity |
| Fast tracking      | over *id* *X*%              | over enable-jenkins-job 15% | How much activity can be overlapped with it's predecessors |

The exact meaning of resource assignment attribute (@) depends on presense of "parallel" attribute (denoted with `||`):
* with `||` (or `|| NUMBER`) - developers can work on task in parallel (e.g. it consists of many similar unrelated chunks)
* without - only one of specified engineers will be selected to work on a task

For example, this activity
```
|<-  // @yura/slava/max, 2h-1d
```
can be done either by "yura", "slava" or by "max" (but not both simultaneously) and may require 2 hours to 2 days of effort.
Adding `||` (or `|| 3`) would mean that all three developers will be able to work on parallel.
Adding `|| 2` would mean that any two of them will be able to work in parallel.

Note that you can not
* assign names to activities (this forces you to focus on goals rather than tasks)
* assign resources or efforts to goals (these are instantaneous events so they do not take any time to "accomplish")

# Development

Install in editable mode via
```
python3 -mpip install -e .
```

To test, install `pytest-3` and run
```
$ pytest-3 gaplan
```

# TODO

High prio:
* Implement simple scheduler (work-in-progress)
* Export to MS Project (Project Elements and XML Structure: https://msdn.microsoft.com/en-us/library/bb968652%28v=office.12%29.aspx).

Other:
* Docstrings.
* Use f-strings.
* Fix remaining TODO and FIXME.
* Add (many) more unittests.
* Add Travis, codecov.
* Mark time- or risk-critical paths in PERT diagram.
* Add include directives.
* Describe tracking info (actual efforts and durations, Jira tasks, etc.) in README.
* Fast tracking in TJ.
