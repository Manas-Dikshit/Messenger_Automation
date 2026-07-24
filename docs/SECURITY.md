# Security

## 1. What's Sensitive Here

| Asset | Sensitivity | Where it lives |
|---|---|---|
| SMS Gateway Cloud username/password | High - grants ability to send SMS from the teacher's phone | GitHub Actions **Secrets** only |
| Contact phone numbers (CSV) | Moderate - personal data | Committed to the repository (make the repo **private**) |
| Sent-state file | Low | Committed to the repository |

## 2. Why GitHub Secrets

GitHub Actions **repository Secrets** are encrypted at rest, only
decrypted into the runner's environment at execution time, and are
automatically redacted from workflow logs if they ever appear in
output. They are never exposed to pull requests from forks unless
explicitly configured to be. This is why credentials are read
exclusively via environment variables (`SMS_GATEWAY_USERNAME`,
`SMS_GATEWAY_PASSWORD`) in `config.py`, and never hardcoded or placed
in the CSV.

## 3. Setting Up Secrets

1. Go to your repository → **Settings** → **Secrets and variables** →
   **Actions**.
2. Under **Secrets**, click **New repository secret**.
3. Add:
   - `SMS_GATEWAY_USERNAME`
   - `SMS_GATEWAY_PASSWORD`
4. (Optional) Under **Variables** (not Secrets, since these aren't
   sensitive), add:
   - `SMS_GATEWAY_BASE_URL` (only if self-hosting the relay)
   - `BIRTHDAY_TIMEZONE` (e.g. `Asia/Kolkata`)

## 4. Credential Storage

- Credentials are never written to disk by this project outside of
  process memory during a run.
- `.env` is listed in `.gitignore` - a local `.env` file (copied from
  `.env.example`) is only for developer testing and must never be
  committed.
- The repository itself should be set to **Private** if the CSV
  contains real names, phone numbers, or addresses, since GitHub
  Secrets protect credentials but do **not** encrypt file contents in
  the repo - the CSV is visible to anyone with repo read access.

## 5. Encryption & Transport

- All communication with the SMS Gateway Cloud API occurs over HTTPS
  (TLS). The `requests` library validates the server's TLS certificate
  by default, and this project does not disable that verification
  anywhere.
- GitHub Secrets are encrypted at rest using a per-repository
  encryption process managed by GitHub (libsodium sealed boxes for
  the initial write; encrypted storage thereafter).

## 6. Authentication

- The SMS Gateway Cloud API uses HTTP Basic Authentication. Credentials
  are sent only over HTTPS, only to the configured `SMS_GATEWAY_BASE_URL`
  host, and only for the single `/messages` POST call needed to send a
  text.
- A 401/403 response is treated as a **non-retryable** authentication
  failure (`SmsGatewayAuthenticationError`) - the client intentionally
  does not retry credential failures, to avoid any appearance of
  credential brute-forcing and to fail fast with a clear log message.

## 7. Least Privilege

- The `daily.yml` workflow requests only `permissions: contents: write`
  - the minimum needed to check out the repo and commit the updated
  sent-state file. It does not request `issues`, `pull-requests`,
  `packages`, or any other GitHub API scope.
- The `lint.yml` workflow requests only `permissions: contents: read`,
  since it never needs to write anything back.
- The SMS Gateway account/credential pair should be dedicated to this
  automation and not reused for the teacher's personal login to the
  app, if the app supports creating a separate Cloud API credential.

## 8. Rotating Credentials

If you suspect the SMS Gateway credentials have leaked (e.g. an
accidental commit, a compromised collaborator account):

1. Open the SMS Gateway for Android app → **Settings** → **Cloud
   Server** → **3rd party API** tab.
2. Generate/reset the API password (the app supports regenerating this
   without reinstalling).
3. Update the `SMS_GATEWAY_PASSWORD` GitHub Secret with the new value
   (Settings → Secrets and variables → Actions → edit the secret).
4. Trigger a manual `workflow_dispatch` run with `dry_run: true` to
   confirm the new credentials authenticate successfully before
   relying on the next scheduled run.

## 9. Revoking Credentials

To fully revoke access (e.g. decommissioning the automation, or the
phone was lost/stolen):

1. In the SMS Gateway app, disable or delete the Cloud Server
   connection entirely, or log out of Cloud Mode.
2. Delete the `SMS_GATEWAY_USERNAME`/`SMS_GATEWAY_PASSWORD` secrets
   from the GitHub repository.
3. Disable or delete the `daily.yml` workflow (rename it to
   `daily.yml.disabled` or delete the file) so scheduled runs stop
   attempting to authenticate.

## 10. Reporting a Security Issue

If you find a security issue in this project itself (not in the
third-party SMS Gateway app), please open a private security advisory
on the repository (GitHub → Security → Advisories → **Report a
vulnerability**) rather than a public issue, so it can be addressed
before public disclosure.
