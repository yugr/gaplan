_This is work-in-progress._

Gaplan includes a simple experimental scheduler which is driven
by scheduling plan defined by the user.
The plan is a hierarchy of _scheduling blocks_.
Each block specifies which goals (or subblocks) should be scheduled,
whether they need to be executed in parallel or sequentially
and by whom.

Example plan:
```
# Schedule blocks below in parallel with each other
# and ensure that it's completed by end of May
||  // deadline 2020-04-30  
  |Implement X
  |Integrate Y
  # Goals in next block are scheduled sequentially
  # and must be implemented by members of "experts" team
  # (2 developers can work in parallel on each task).
  --  // @experts, || 2
    |Convert test data Z
    |Implement backend for Z
```
