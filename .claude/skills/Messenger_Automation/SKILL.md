```markdown
# Messenger_Automation Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill covers the core development patterns and workflows found in the **Messenger_Automation** Python repository. The codebase automates messaging tasks, tracks message delivery states, and is structured for maintainability and clarity. You'll learn the project's coding conventions, how to manage sent state data, and how to follow the repository's workflow for updating message records.

## Coding Conventions

**File Naming**
- Use camelCase for filenames.
  - Example: `messageSender.py`, `userManager.py`

**Import Style**
- Use relative imports within modules.
  - Example:
    ```python
    from .utils import formatMessage
    ```

**Export Style**
- Use named exports (explicitly define what is exported).
  - Example:
    ```python
    def sendMessage(user, message):
        # send logic
        pass

    __all__ = ['sendMessage']
    ```

**Commit Messages**
- Prefix with `data` or `feat` when relevant.
- Keep messages concise (average ~50 characters).
  - Example: `data: reset sent state for all users`
  - Example: `feat: add message scheduling feature`

## Workflows

### Update Sent State Data
**Trigger:** When you need to update or reset the record of which users have been messaged.
**Command:** `/update-sent-state`

1. Open `data/.sent_state.json`.
2. Add, update, or clear entries to reflect which users have been sent messages.
   - Example entry:
     ```json
     {
       "user123": "2024-06-12T10:15:00Z",
       "user456": "2024-06-13T08:00:00Z"
     }
     ```
   - To reset, clear the file or remove specific users.
3. Save your changes.
4. Commit with a descriptive message, e.g., `data: reset sent state for June campaign`.
5. Push your changes to the repository.

## Testing Patterns

- Test files follow the pattern `*.test.*` (e.g., `messageSender.test.py`).
- The specific test framework is not detected, but typical Python test frameworks like `unittest` or `pytest` are likely suitable.
- Place tests alongside the modules they test or in a dedicated test directory.

**Example Test File:**
```python
# messageSender.test.py

from .messageSender import sendMessage

def test_send_message():
    assert sendMessage("user123", "Hello!") == True
```

## Commands

| Command             | Purpose                                                          |
|---------------------|------------------------------------------------------------------|
| /update-sent-state  | Update or reset the sent state for message recipients            |
```
