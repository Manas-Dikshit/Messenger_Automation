---
name: update-sent-state-data
description: Workflow command scaffold for update-sent-state-data in Messenger_Automation.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /update-sent-state-data

Use this workflow when working on **update-sent-state-data** in `Messenger_Automation`.

## Goal

Tracks or resets the sent state for message recipients, likely to manage which users have been sent messages.

## Common Files

- `data/.sent_state.json`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit data/.sent_state.json to add, update, or clear sent state entries
- Commit the changes with a descriptive message

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.