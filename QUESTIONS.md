Some open questions about declarative planning. Please share if you have answers or comments.

* artificial intermediate goals (like "All requirements for target fullfilled")
  to get to single activity:
```
|Some goal
|<-  // 1d-2d
   |<-
      |Prerequisite 1
   |<-
      |Prerequisite 2
```
* parameterized subnets e.g.
    * some tests and deployment activities need to be performed for each release
    * or same actions have to be performed for a family of features
  how to specialize such parameterized networks (i.e. override subgoals) especially
  as project evolves and individual instances are subdivided.
* projection errors when making estimates i.e. estimator estimates
  based on his own idea of who'll work on a task
* overlap between tasks e.g. testing/debugging can be done roughly in parallel with testsuite preparation:
```
|All tests pass
|<-
   |Testsuite ready
```
