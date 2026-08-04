# Setup Guide — Get This Running From Zero

This guide assumes you know nothing about this project yet. Follow
the steps in order — by the end, birthday SMS messages will be
sending automatically, every day, forever, for free.

**Total time needed: about 20–30 minutes.**

---

## What You'll Need Before Starting

- [ ] A GitHub account (free) — [github.com](https://github.com)
- [ ] An Android phone with an active SIM card (this phone will be
      the one actually sending the texts — pick one that stays
      charged and connected to the internet/mobile data most of the time)
- [ ] Your contact list — names, phone numbers, and birthdays (an
      Excel sheet is fine, we'll convert it)

---

## Step 1 — Get a Copy of This Project

If you were given a link to this repository already, skip to Step 2.

Otherwise:
1. Go to the repository's page on GitHub.
2. Click the **Fork** button (top right) — this makes your own copy
   under your account.
3. Note your fork's URL, e.g. `https://github.com/<Manas-Dikshit>/Messenger_Automation`.

---

## Step 2 — Install "SMS Gateway for Android" on the Sending Phone

This is the app that lets our script send real texts through that
phone's SIM.

1. On the Android phone, download the app:
   [github.com/capcom6/android-sms-gateway/releases/latest](https://github.com/capcom6/android-sms-gateway/releases/latest)
   (Look for the `.apk` file under "Assets".)
2. Open the downloaded file to install it. If Android warns about
   "installing from unknown sources," allow it — this is expected
   for apps installed outside the Play Store.
3. Open the app. Grant it SMS permission when asked (it cannot send
   texts without this).
4. Inside the app, find **Settings → Cloud Server**.
5. Turn on **Cloud Mode**.
6. Go to the **"3rd party" tab** inside Cloud Server settings.
7. You'll see (or can generate) a **username** and **password**.
   **Write these down somewhere safe** — you'll need them in Step 4.
   Treat them like a real password: don't share them or paste them
   anywhere public.
8. Leave the app running in the background. It needs to be
   reachable by the internet (Wi-Fi or mobile data) at the moment
   messages are meant to send — keep the phone on and connected.

Full details/screenshots: [`docs/SMS_GATEWAY_SETUP.md`](SMS_GATEWAY_SETUP.md)

---

## Step 3 — Prepare Your Contact List

The app reads contacts from a file: `data/birthdays.csv`.

1. Open `data/birthdays.csv` in the repository (on GitHub, click the
   file, then "Edit"; or clone the repo and open it in Excel/any
   text editor).
2. It's a simple table with these columns:

   | Column | Required? | What Goes Here |
   |---|---|---|
   | `Name` | Yes | Full name |
   | `PhoneNumber` | Yes | Phone number **with country code**, e.g. `+919876543210` |
   | `Birthday` | Yes | Date, preferably `YYYY-MM-DD` (e.g. `1999-05-16`) |
   | `Classification` | No | Free text label, e.g. "Student", "Colleague" |
   | `Brief` | No | Any short note |
   | `Address` | No | Free text |
   | `Enabled` | No | Leave blank, or write `FALSE` to pause messages to just this person |
   | `LastSent` | No | Leave blank — this is informational only |
   | `MessageTemplate` | No | Leave blank to use the default message, or write a custom one just for this person |

3. If your birthday data doesn't include the year (only day and
   month are known), use a clearly fake placeholder year like
   `1900-05-16` — the system only checks month + day for matching,
   so this is completely fine.
4. If starting from an Excel file: in Excel, use **File → Save As →
   CSV (Comma delimited)**, matching the column headers above exactly.
5. Save/commit this file back into the repository.

**Example row:**
```
Name,PhoneNumber,Birthday,Classification,Brief,Address,Enabled,LastSent,MessageTemplate
Rahul Sharma,+919876543210,1999-05-16,Student,Class 10,Kolkata,TRUE,,
```

---

## Step 4 — Add Your Credentials as GitHub Secrets

The username/password from Step 2 must never be typed directly into
any file in the repository. Instead, GitHub has a secure vault for
this called "Secrets."

1. On GitHub, open your repository.
2. Go to **Settings → Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Create one named exactly `SMS_GATEWAY_USERNAME` — paste the
   username from Step 2 — save.
5. Click **New repository secret** again.
6. Create one named exactly `SMS_GATEWAY_PASSWORD` — paste the
   password from Step 2 — save.

That's it — these values are now securely stored and only used
inside GitHub's automation, never visible in logs or code.

---

## Step 5 — Customize the Message (Optional)

By default, every birthday message uses one template, defined in
`src/birthday_sms/constants.py` (the `DEFAULT_MESSAGE_TEMPLATE`
value). You can change the wording there directly, or override it
without editing code by adding a **repository variable** (Settings →
Secrets and variables → Actions → **Variables** tab → New variable
named `DEFAULT_MESSAGE_TEMPLATE`).

Available placeholders you can use in the message text:

| Placeholder | Becomes |
|---|---|
| `{NAME}` | Full name |
| `{FIRST_NAME}` | First word of the name |
| `{TODAY}` | Today's date |
| `{YEAR}` | Current year |
| `{CLASSIFICATION}` | The Classification column value |
| `{BRIEF}` | The Brief column value |

(Avoid `{AGE}` unless every contact's `Birthday` has a real, correct
year — if years are placeholders like `1900`, `{AGE}` will render a
nonsense number.)

---

## Step 6 — Test Before Going Live

Never skip this step. Two ways to test:

**A. Dry run (safest — renders messages but sends nothing):**
1. On GitHub, go to the **Actions** tab.
2. Click **Daily Birthday SMS** in the left sidebar.
3. Click **Run workflow** (top right).
4. Set `dry_run` to `true`, click the green **Run workflow** button.
5. Wait ~30 seconds, click into the run, open the log, and confirm
   it correctly identifies any birthdays and shows what message
   *would* have been sent.

**B. Real send test to your own number:**
See [`README.md`](../README.md#manual-instant-test-real-sms-right-now)
for the full manual-test recipe — temporarily set your own number's
birthday to today's date, run the send once, confirm you receive
the real SMS, then revert the test change.

---

## Step 7 — You're Live

Once tested, do nothing else — the system runs itself:

- Every day, GitHub automatically checks the contact list.
- If it's someone's birthday, a message is sent right at midnight
  (in the timezone configured — default `Asia/Kolkata`).
- Each send is recorded so nobody gets double-texted.
- To add, remove, or edit contacts going forward: just edit
  `data/birthdays.csv` directly on GitHub anytime.

## Keeping It Running

- **Keep the sending phone charged and connected** — if it's off or
  offline at midnight, that day's messages will fail (it will still
  retry automatically a few times before giving up).
- **If you ever reinstall the app or reset the phone**, generate a
  new username/password in Step 2 and update the two GitHub Secrets
  from Step 4 to match.
- **If something isn't working**, check
  [`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md) first.

---

## Quick Reference — Where Everything Lives

| I want to... | Go here |
|---|---|
| Add/edit/remove a contact | `data/birthdays.csv` |
| Change the message wording | `src/birthday_sms/constants.py`, or a `DEFAULT_MESSAGE_TEMPLATE` repo variable |
| Change what time messages send | `.github/workflows/daily.yml` (cron line) + `BIRTHDAY_TIMEZONE` |
| Update gateway login | GitHub Settings → Secrets and variables → Actions |
| Manually trigger a run | GitHub → Actions tab → Daily Birthday SMS → Run workflow |
| See what happened on a past run | GitHub → Actions tab → click any past run → view logs |
