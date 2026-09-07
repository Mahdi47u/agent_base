# Contributing

Use focused branches and Conventional Commits (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`, or `ci`). Keep unrelated changes separate.

Before opening a pull request:

1. Explain the boundary being changed.
2. Add or update the closest deterministic tests.
3. Run backend tests/lint/migration check and frontend tests/typecheck/build.
4. Update docs for contract, configuration, or workflow changes.
5. Verify no `.env`, database, provider key, cookie, or private endpoint is staged.

Provider smoke tests must be opt-in and must use synthetic data. Never make CI depend on a paid model response.
