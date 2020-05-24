In addition to goals you should specify project and resource information.
This is done via set of attributes normally specified at start of the file
e.g.
```
name = MyProject
start = 2020-02-01
finish = 2020-06-01
members = alice, bob (0.75), carol
teams = experts (alice), developers (alice, bob), testers (carol)
```

Here is a list of all supported attributes:

| Attribute      | Value syntax                                | Example                                         | Comment             |
|----------------|---------------------------------------------|-------------------------------------------------|---------------------|
| name           |                                             | `name = MyProject`                              | Project name        |
| start          | *YYYY-MM-DD*                                | `start = 2020-02-01`                            | Project start date  |
| finish         | *YYYY-MM-DD*                                | `finish = 2020-06-01`                           | Project finish date |
| members        | *dev1*, *dev2 (efficiency2), ...*           | `members = alice, bob (0.75)                    | Project members and their efficiencies (default efficiency is 100%) |
| teams          | *team1 (dev1, ...), team2 (dev2, ...), ...* | `teams = experts (alice, bob), testers (carol)` | Teams and their members (there's default team `all` which holds all developers) |
