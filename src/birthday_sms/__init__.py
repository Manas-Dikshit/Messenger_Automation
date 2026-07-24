"""Birthday SMS Automation.

A production-grade system that reads a contacts CSV, finds today's
birthdays, and sends SMS messages via a self-hosted SMS Gateway for
Android (capcom6/sms-gateway) instance running in Cloud Mode, from the
teacher's own SIM card. Designed to run on a schedule via GitHub
Actions, with no PC or server required to stay online.
"""

__version__ = "1.0.0"
