# memorization_app Repository Notes

## Product and Data

- The app uses Streamlit on Python 3.12; read `progress.md` before non-trivial work.
- Keep Supabase credentials server-side and never expose or log secret values.
- Health checks must remain read-only.
- Live smoke tests use the `codex-maintenance` account and must clean up their temporary records; never assume another user is a test account.
- Preserve `daily_assignments` compatibility and the documented fallback when its migration is not present.

## Validation

- The standard local release gate is `.venv\Scripts\python.exe scripts\check.py`.
- Credentialed Supabase live smoke is a separate close-out check when the changed path requires it.
