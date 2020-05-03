Some open questions about declarative planning. Please share if you have answers or comments.

* Since early days of PERT it was noticed that we often need
  to introduce meaningless intermediate goals like
  "All requirements for target fullfilled" in this example:
```
|Some goal
|<-  // 1d-2d
   |All requirements for target fullfilled
   |<-
      |Prerequisite 1
   |<-
      |Prerequisite 2
```
  Gaplan searches this by introducing anonymous ("dummy" in PERT terminology) goals:
```
|Some goal
|<-  // 1d-2d
   |<-
      |Prerequisite 1
   |<-
      |Prerequisite 2
```
* Parts of network often have isomorphic structure e.g.
    * common set of verification and deployment activities needs
      to be performed for each release
    * same technology (i.e. sequence of actions) is used for a family of features
  Can this commonality be expressed via parameterized subnetwork ("network functions")?
  How can we specialize such parameterized networks (override subgoals, attributes, etc.)
  especially as project evolves and individual instances are subdivided.
* How can we avoid projection errors when making estimates i.e. estimator estimates
  based on his own idea of who'll work on a task.
* Would it make sense to keep a set of estimates from different estimators
  and select a strategy for combining them?
* What's the best way to represent overlap (i.e. "fast tracking") between tasks?
  E.g. testing/debugging can often be done roughly in parallel
  with testsuite preparation.
  Ordinary dependencies are too inflexible for this:
```
|Feature ready
|<-
   |Feature developed
   |<-  // 2w-1m
|<-
   |Feature tested
   |<-  // 2w-1m
      |Feature developed
```
  Traditional PERT approach is to introduce intermediary goals:
```
|Feature ready
|<-
   |Feature partially developed
   |[] ...
   |<-  // 1w-2w
|<-
   |Feature developed
   |<-  // 1w-2w
      |Feature partially developed
|<-
   |Feature partially tested
   |<-  // 1w-2w
      |Feature partially developed
|<-
   |Feature tested
   |<-  // 1w-2w
      |Feature developed
```
  but this requires a lot of boilerplate.
  Gaplan provides alternative approach: `over` directive:
```
|Feature ready
|<-
   |Feature developed
   |<-  // 2w-1m, id feature-dev
|<-
   |Feature tested
   |<-  // 2w-1m, over feature-dev 50%
      |Feature developed
```
* Often developers work on task occasionally on different dates
  so duration is broken to many small intervals which in practice
  can not be tracked. Gaplan provides means to specify total duration
  and actual "ideal hours" (i.e. real time spent on task):
```
# Developer has been working on a feature for 1 work week
# in parallel with other tasks and spent 2 days in total.
|Feature ready
|<-  // 1d-1w (2d), 2020-01-13 - 2020-01-18
```
  It's unclear whether this is enough in practice.
* For generating nice MSP/TJ reports it's important to somehow infer
  hierarchy for goals (i.e. WBS). Gaplan currently does this heuristically:
  if goal is defined within another goal, it's considered to be a WBS child.
  E.g. both "Feature implemented" and "Feature tested" are children of
  "Feature ready" but "Another feature ready" is not:
```
|Feature ready
|<-
   |Feature implemented
|<-
   |Feature tested

|Another feature ready
|<-
   ...
```

