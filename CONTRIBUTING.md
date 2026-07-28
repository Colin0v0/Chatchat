# Contributing to Chatchat

Thank you for contributing to Chatchat.

## Before opening a pull request

1. Keep changes focused and document any user-visible behavior change.
2. Do not commit `.env` files, API keys, user data, or contents from `storage/`.
3. Run the relevant checks:

   ```bash
   PYTHONPATH=backend python -m pytest backend/tests
   cd frontend && pnpm build
   ```

4. Describe the problem, solution, and verification in the pull request.

## Issues

Use issues for reproducible bugs, feature proposals, and documentation improvements. Do not include secrets or private user data in an issue.
