# v1.8 continuation checkpoint

## Completed and actually executed
- Generated `mgl_v18_dependency.csv`: 22 unresolved ending requirement profiles (stats, education, project, event, EAR and social conditions).
- Executed `python -m unittest discover -s tests -q`: 17 tests passed.
- Preserved all original game data and gameplay code in this checkpoint.

## Not completed
- New 120-month witness searches for unresolved endings.
- Controlled v1.7 versus v1.8 same-seed comparison.
- Additional recommendation algorithm changes (not made without measured comparison).

## Reproduce
`python mgl_v18_dependency.py`
`python -m unittest discover -s tests -q`
