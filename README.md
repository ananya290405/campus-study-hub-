# CampusNotes Enhanced

A polished Flask notes-sharing app with search, subject filters, statistics, sortable notes, grid/list view, theme toggle, and drag-and-drop upload selection.

## Run locally
1. Install Python 3.10+.
2. Run `pip install -r requirements.txt`
3. Run `python app.py`
4. Open `http://127.0.0.1:5000`

Local demo mode stores files under `local_data/`. This is not persistent storage on ephemeral hosting platforms.

## Render deployment
Commit the contents of this folder to your existing GitHub repository. Build command: `pip install -r requirements.txt`. Start command: `gunicorn app:app`.

## Optional AWS mode
The existing backend supports S3 + DynamoDB when `BUCKET` and `TABLE` are configured and valid AWS credentials/permissions are supplied. Do not add AWS keys directly to source code. Cloud mode has not been configured by this package.


## Extra study features
- Save/bookmark notes in the current browser.
- Study planner with tasks, completion checkboxes and remove actions.
- Built-in quick revision quiz about cloud-computing fundamentals.
- These three features use browser localStorage; they are device/browser-specific and are not shared across users.
- Existing core note upload/download storage remains local demo mode by default, or optional S3 + DynamoDB when configured.
