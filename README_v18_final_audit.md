# MGL v1.8 final audit checkpoint

- `mgl_v18_selection_audit.csv`: 44 targeted witness paths replayed from recorded seeds/modes, with actual selected ending.
- `mgl_v18_selection_audit.json`: 44/44 eligible and selected matches; 22 unique target endings; 0 mandatory transfer violations.
- `mgl_v18_final_audit.py`: deterministic replay implementation.
- `regression_final.log`: unit-test run.

Important limitations:
- 26 other endings have prior eligibility evidence but were not audited for actual selected-ending identity in this pass.
- A complete paired v1.7 vs v1.8 120-month comparison has not yet been run.
- Relationship/career opportunity cost has not been isolated causally.
- Prior reported 568 failed scores are action-outcome failures, not necessarily invalid actions.
