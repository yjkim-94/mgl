# MGL v1.8 dependency graph audit checkpoint

- Run `python mgl_v18_graph_audit.py` to recursively traverse prerequisite projects and events for the 22 previously unresolved endings.
- `mgl_v18_graph_audit.csv`: topological node order, required maximum education/stat thresholds, age, AP and cost lower bounds.
- `mgl_v18_graph_issues.csv`: missing references and dependency cycles.
- These are **static** checks, not 120-month success-path simulations; AP/cost totals cover project/event nodes only.
- No game requirements or content have been changed.
- Run regression tests: `python -m unittest discover -s tests -q`.
