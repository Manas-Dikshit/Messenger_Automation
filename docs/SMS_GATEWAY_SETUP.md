# SMS Gateway for Android - Setup Guide

This project sends SMS through **SMS Gateway for Android™** by
capcom6 (open source), running in **Cloud Mode**. This document walks
through setting it up on the teacher's phone from scratch.

## 1. Installation

1. On the teacher's Android phone, install **SMS Gateway for Android**
   from the Google Play Store, or sideload the APK from the project's
   official GitHub Releases page if preferred.
2. Open the app once installed.

*(Screenshot placeholder: app icon on home screen after install.)*

## 2. Required Permissions

On first launch, the app requests:

- **SMS** - required to actually send text messages.
- **Phone state** - used to detect SIM/carrier status.
- **Notifications** - used to show a persistent "gateway running"
  notification (required by Android for reliable background operation).

Grant all requested permissions. Without SMS permission, the app
cannot send anything regardless of API configuration.

*(Screenshot placeholder: Android permission request dialogs.)*

## 3. Battery Optimization

Android aggressively kills background apps to save battery, which can
silently break Cloud Mode's persistent connection.

1. Go to **Android Settings → Apps → SMS Gateway for Android → Battery**.
2. Select **Unrestricted** (exact wording varies by manufacturer -
   Samsung, Xiaomi, and OnePlus all use slightly different menus; look
   for "Don't optimize" or "No restrictions").
3. If your device has a separate "Auto-start" or "Protected apps" list
   (common on Xiaomi/MIUI, Oppo, Vivo), enable auto-start for the app
   as well.

*(Screenshot placeholder: battery optimization exclusion screen.)*

## 4. Cloud Mode vs. Local Mode

The app supports two modes:

| Mode | How it works | Suitable here? |
|---|---|---|
| **Local Mode** | App exposes a local HTTP server on the phone's own IP; caller must be on the same network | No - GitHub Actions runners are not on the same network as the phone |
| **Cloud Mode** | App maintains an outbound connection to a cloud relay (`api.sms-gate.app`); caller sends requests to the cloud API, which forwards to the phone | **Yes - this is what this project uses** |

## 5. Enabling Cloud Mode

1. In the app, go to **Settings → Cloud Server**.
2. Toggle **Enable Cloud Server** on.
3. The app will register with the cloud relay and display a
   **Cloud Server connected** status once online.

*(Screenshot placeholder: Cloud Server settings screen showing "Connected" status.)*

## 6. Creating API Credentials

1. Still under **Settings → Cloud Server**, open the **3rd party API**
   (or **API access**) tab.
2. Note the generated **username** and **password** (or generate a new
   password if none exists yet).
3. These are the exact values to store as the `SMS_GATEWAY_USERNAME`
   and `SMS_GATEWAY_PASSWORD` GitHub Secrets - see
   [`SECURITY.md`](SECURITY.md).

*(Screenshot placeholder: API credentials screen with username/password fields.)*

## 7. Testing the Connection

Before wiring up GitHub Actions, verify the credentials work with a
simple manual request. Replace the placeholders and run:

```bash
curl -u "YOUR_USERNAME:YOUR_PASSWORD" \
  -X POST "https://api.sms-gate.app/3rdparty/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message from curl", "phoneNumbers": ["+91XXXXXXXXXX"]}'
```

A successful response looks like:

```json
{
  "id": "some-message-id",
  "state": "Pending",
  ...
}
```

If the recipient phone receives the test SMS, Cloud Mode is fully
working end-to-end. If not, see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

## 8. Verifying the Phone Is Online

- The app's home screen shows a **connection status indicator**
  (typically a colored dot or "Connected"/"Disconnected" label) for
  the Cloud Server connection.
- The cloud API's dashboard (if the capcom6 hosted service provides
  one) may also show device online/offline status.
- Programmatically, an authentication-successful-but-delivery-failed
  response from `/messages` (device unreachable) will surface in this
  project's logs as a retried, then eventually failed, send - see the
  `Failure Scenarios` table in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 9. Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| App shows "Disconnected" | No internet, or battery optimization killed the app | Reconnect Wi-Fi/data; re-check battery settings (Section 3) |
| `curl` test returns 401 | Wrong username/password | Regenerate credentials in the app, update secret |
| `curl` test returns 200 but no SMS arrives | SMS permission revoked, or SIM has no signal/credit | Re-check permissions; verify SIM has signal and SMS balance |
| Works via `curl` but not from GitHub Actions | Secrets not set, or workflow env var name mismatch | Confirm secret names exactly match `SMS_GATEWAY_USERNAME`/`SMS_GATEWAY_PASSWORD` |

## 10. Migrating to a New Phone

If the teacher gets a new phone:

1. Install the app on the new phone and repeat Sections 1-6.
2. The new phone will receive **new** API credentials (or you can
   regenerate the existing account's password to point at the new
   device, depending on how the app's account model works - check the
   app's own docs for whether devices or accounts hold the credential).
3. Update the `SMS_GATEWAY_USERNAME`/`SMS_GATEWAY_PASSWORD` secrets in
   GitHub to match.
4. Uninstall the app from the old phone (or disable Cloud Mode there)
   to fully retire it.
5. Trigger a manual `workflow_dispatch` run with `dry_run: true` to
   confirm the new setup authenticates before the next scheduled run.
