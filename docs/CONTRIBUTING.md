# Contributing

Thanks for considering a contribution.

## Development Setup

```bash
git clone https://github.com/<your-username>/birthday-sms-automation.git
cd birthday-sms-automation
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

## Running Tests

```bash
export SMS_GATEWAY_USERNAME=test
export SMS_GATEWAY_PASSWORD=test
pytest --cov=birthday_sms --cov-report=term-missing
```

## Code Style

This project uses `black` (formatting), `isort` (import order), and
`flake8` (linting), all enforced in CI via `.github/workflows/lint.yml`.

```bash
black src tests
isort src tests
flake8 src tests
```

## Making Changes

1. Fork the repository and create a feature branch.
2. Add or update tests for any behavior change.
3. Ensure `black`, `isort`, `flake8`, and `pytest` all pass locally.
4. Open a pull request describing the change and why it's needed.

## Writing GitHub Actions Steps That Auto-Commit

If a workflow step commits a file back to the repo (as `daily.yml`
and `keepalive.yml` do), always `git add` the file **before** checking
whether anything changed, and check the staged diff:

```bash
git add path/to/file
if ! git diff --cached --quiet -- path/to/file; then
  git commit -m "..."
  git push
fi
```

Checking `git diff --quiet` (without `--cached`, before `git add`)
only compares already-**tracked** files - a brand-new, never-before-
committed file is invisible to it, so the very first run silently
skips the commit every single time. This exact bug shipped in an
earlier version of `keepalive.yml` and was only caught by manually
testing the workflow and finding no commit ever landed.

## Reporting Bugs

Open a GitHub Issue with:
- What you expected to happen.
- What actually happened (include the relevant log lines - redact any
  phone numbers or personal data first).
- Whether it happens in `dry_run` mode too.

## Security Issues

Please do **not** open a public issue for security vulnerabilities -
see the reporting process in [`SECURITY.md`](SECURITY.md).
