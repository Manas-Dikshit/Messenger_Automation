# External Scheduler Setup Guide (cron-job.org)

GitHub Actions' own `schedule:` trigger has no timing guarantee - per
[GitHub's docs](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule),
it "can be delayed during periods of high loads," and under heavy
load "some queued jobs may be dropped" entirely. This project observed
delays of 1.5+ hours and at least one dropped run in testing.

`workflow_dispatch` (the same trigger used by the "Run workflow"
button) has no such delay - it runs promptly, every time. This guide
sets up [cron-job.org](https://cron-job.org) (free) to call that
trigger via GitHub's REST API on a precise schedule, so the actual
send time no longer depends on GitHub's internal queue.

GitHub's own `schedule:` cron is left in place as a free backup in
both workflows (except `cron_ping.yml` - see the note near the end).
The dedupe logic in `state_store.py` means there's no risk of a
duplicate SMS if both happen to fire the same day.

> **Every `YOUR_TOKEN` (or `Bearer YOUR_TOKEN`) placeholder in this
> guide must be replaced with your actual token before running the
> command or saving the header** - commands and configs left with
> the literal placeholder text will fail authentication. Type the
> real value directly into your terminal or cron-job.org's field;
> never paste the filled-in command anywhere else (chat, issues,
> screenshots, commit messages) once it contains the real token.

## 1. Create a GitHub Personal Access Token

This token is what proves to GitHub that cron-job.org's request is
allowed to trigger a run on your repo. Scope it as tightly as
possible - it should only be able to do this one thing.

1. Go to **https://github.com/settings/tokens?type=beta** (Fine-grained
   tokens page).
2. Click **Generate new token**.
3. **Token name**: something identifiable, e.g. `cronjob-org-trigger`.
4. **Expiration**: select **No expiration**. Fine-grained tokens
   support this option despite GitHub's UI nudging toward a fixed
   date - it avoids the token silently lapsing and breaking the
   scheduler with no warning. The tradeoff: it's a standing
   credential until you manually revoke it, so the tight repo/
   permission scoping from step 6-7 matters more, not less. If you'd
   rather rotate periodically anyway, pick a date and note it
   somewhere you'll actually see again.
5. **Resource owner**: your account.
6. **Repository access** → **Only select repositories** → choose your
   fork/repo (e.g. `your-username/Messenger_Automation`).
7. Scroll to **Permissions** → **Repository permissions** → find
   **Actions** → change from "No access" to **Read and write**.
   Leave every other permission at "No access."
8. Scroll down, click **Generate token**.
9. **Copy the token immediately** - it is shown once only. It looks
   like `github_pat_11AbCXyz...` (a long string). If you navigate
   away before copying it, you must generate a new one.

**Never paste this token into chat, a screenshot, an issue, or a
commit.** If it's ever exposed that way, treat it as compromised -
revoke it immediately (same Fine-grained tokens page → find it →
**Delete**) and generate a fresh one. Type it directly into
cron-job.org's field instead of copying it anywhere else first.

### Verify the token works, before touching cron-job.org

Run this in your own terminal (not here in chat with anyone), with
your real token substituted:

```bash
curl -i -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
```

Expect `HTTP/1.1 200 OK` and your GitHub profile as JSON. If this
fails, stop - fix the token before continuing (regenerate if unsure).

Then verify it can actually trigger a dispatch (this doubles as a
real trigger, so only run it when you're ready to test the full
pipeline):

```bash
curl -i -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "Content-Type: application/json" \
  -d '{"ref":"main"}' \
  https://api.github.com/repos/<owner>/<repo>/actions/workflows/daily.yml/dispatches
```

Expect `HTTP/1.1 204 No Content`. This proves the token, permission
scope, and URL are all correct - independent of cron-job.org
entirely. If this curl works but cron-job.org later doesn't, the
problem is in cron-job.org's configuration, not GitHub's side.

## 2. Create a cron-job.org Account

1. Go to **https://cron-job.org**.
2. Click **Sign up** - email + password, free.
3. Verify your email if prompted, then log in.

## 3. Create the Job for `daily.yml`

1. Dashboard → **Create cronjob**.
2. **Title**: `Daily Birthday SMS trigger`.
3. **URL**:
   ```
   https://api.github.com/repos/<owner>/<repo>/actions/workflows/daily.yml/dispatches
   ```
4. **Execution schedule** → select **"Every day at"** → set the time
   in **UTC** to match your `daily.yml` cron line (e.g. `18:40` UTC
   for a 00:10 IST send - convert your local time to UTC).
5. Open the **Advanced** tab:
   - **Requires HTTP authentication**: leave this **OFF**. This is a
     separate Basic-Auth feature, unrelated to what we're doing here.
     Leaving it on with empty username/password fields commonly
     causes a generic *"non-well-formed job"* error on save.
   - **Request method**: explicitly select **POST**. Some UIs default
     silently to GET, which returns a `404 Not Found` from GitHub -
     this endpoint only accepts POST, and GitHub returns the same
     404 for any other method (indistinguishable from a genuinely
     wrong URL, which is a common point of confusion).
   - **Headers** → add four rows:

     | Key | Value |
     |---|---|
     | `Authorization` | `Bearer YOUR_TOKEN` |
     | `Accept` | `application/vnd.github+json` |
     | `Content-Type` | `application/json` |
     | `X-GitHub-Api-Version` | `2022-11-28` |

   - **Request body**:
     ```json
     {"ref":"main"}
     ```
6. Under **Notify me when...**, turn on "execution of the cronjob
   fails" so you're emailed if something breaks later.
7. Click **Save** / **Create**.

## 4. Test the Job

1. On the job's page, click **Test run**.
2. Expect a success status (`204`).
3. Immediately check your repo's **Actions** tab → **Daily Birthday
   SMS** → a new run triggered by `workflow_dispatch` should appear
   within seconds.

If it fails, see **Troubleshooting** below.

## 5. Create the Job for `cron_ping.yml`

Same steps as above, with two differences:

- URL:
  ```
  https://api.github.com/repos/<owner>/<repo>/actions/workflows/cron_ping.yml/dispatches
  ```
- Schedule: whatever time your `cron_ping.yml` is meant to run
  (e.g. `04:47` UTC for 10:17 IST).

**Important:** `cron_ping.yml` intentionally has **no** `schedule:`
trigger in the workflow file at all - it has no dedupe logic (unlike
`daily.yml`'s per-contact-per-year tracking), so if both GitHub's own
schedule and cron-job.org fired for it, that would be a genuine
duplicate API call to the target endpoint, not just wasted compute.
This means `cron_ping.yml` depends entirely on this external
scheduler (or a manual "Run workflow" click) to run at all.

## 6. Testing With Custom Inputs (optional)

`daily.yml`'s `workflow_dispatch` accepts optional inputs
(`dry_run`, `test_phone_number`). A plain `{"ref":"main"}` body runs
in full production mode (real CSV, real send). To test against a
specific number instead, without touching the real CSV, include an
`inputs` object:

```json
{"ref":"main","inputs":{"test_phone_number":"+91XXXXXXXXXX","dry_run":"false"}}
```

Useful for a one-off manual **Test run** click on a separate test
job, before switching the production job's body back to plain
`{"ref":"main"}`.

## Troubleshooting

**`404 Not Found`**
Almost always means the request wasn't actually sent as POST (see
step 5's Request method note above), even if the URL is correct.
Confirm with the curl command from Section 1 - if that returns `204`
but cron-job.org still 404s, the method setting didn't save.

**`401 Unauthorized` / "endpoint requires authentication"**
The `Authorization` header isn't reaching GitHub correctly. Check:
- Header value is exactly `Bearer <token>` - literal word "Bearer",
  one space, then the token (no quotes, no extra whitespace)
- The header field wasn't left empty in cron-job.org's UI
- The token wasn't truncated when pasted (fine-grained tokens are
  long)

**`403 Forbidden`**
The token doesn't have access to this specific repository/workflow -
most commonly because the token was generated from a different
GitHub account than the one that owns (or collaborates with write
access on) the target repo. Regenerate the token from the correct
account, scoped to the correct repository.

**"Sorry, we couldn't process your request... non-well-formed job"**
Usually the **"Requires HTTP authentication"** toggle being left ON
with empty username/password fields (see step 5). Turn it off.

**Test run succeeds but the workflow doesn't appear in the Actions
tab**
Double-check you're looking at the correct repository/fork - a
`workflow_dispatch` call only affects the exact `owner/repo` in the
URL, which may not be the one you're viewing in your browser.

## Maintenance

- **Token expiration**: if set to "No expiration" (as recommended
  above), there's nothing to renew - but it also means the token
  stays valid forever until manually revoked, so if you ever suspect
  it's leaked, revoking it immediately matters more. If you chose a
  fixed expiry instead, cron-job.org's requests will start returning
  401 once it lapses - regenerate the token and update it in
  cron-job.org's header field (you'll also get a failure email if you
  enabled that notification).
- **Changing the schedule time**: update both the cron line in the
  workflow YAML *and* the time in cron-job.org's job - they're
  independent settings and won't stay in sync automatically.
- See [`SECURITY.md`](SECURITY.md#8a-external-scheduler-credential-cron-joborg-or-similar)
  for the token's blast radius if leaked, and rotation guidance.
