# Hosted deployment status

Updated 2026-09-23. Railway connection verified. Current local changes have NOT
been pushed or deployed. No Railway resources were changed this session.

## Verified Railway state

Workspace: 73156ba1-ff8b-4665-b0c4-2a7c2b6e8387 (nithixs's Projects).

- unique-flow: project 72cfd635-e5d1-4c27-97ec-5077196a54fb, production
  f0df7d8b-b748-4156-9f0c-2c93718bace2, app 4ccf8a57-a390-46a6-b4fe-823efd7fa705.
  No deployment, source, variables or volume. Old start command targets main:app.
- honest-possibility: project d98ed09d-5930-42e0-8d94-bbd7a82499e0, production
  6c1b0a60-dcf7-4f0c-9cd9-63eb543cbdfc, app dd738ae9-606d-4eae-bb1f-dbd0c8902f76.
  Connected to nithixs/XAI-Fake-Review-Detector on main. September 7 deployment
  reports SUCCESS, but is not the current local application. Existing domain:
  https://xai-fake-review-detector-production.up.railway.app (HTTP not verified).
  MySQL eec97601-ac93-4639-8000-3ce097aec181 reports SUCCESS and has a persistent
  500 MB volume at /var/lib/mysql. App defines DB_HOST, DB_NAME, DB_PASSWORD,
  DB_PORT and DB_USER; values were not read.

Asked user which of these two projects to target; answer pending. Publishing is
already authorized. Billing/credit has not been inspected. Obtain approval before
any unapproved paid resource. Railway tools are available; do not reinstall.

## Prepared configuration and checks

- Dockerfile: Node 22 frontend build, Python 3.11 FastAPI runtime, recorded Python
  dependencies. Railway health check /api/health, listening on 0.0.0.0:$PORT.
- .dockerignore allowlists build inputs, excluding secrets and local databases.
- SQLite defaults to /data/reviewguard.db: attach a volume at /data if using it.
  To reuse existing MySQL explicitly set DB_ENGINE=mysql.
- Container SEED_DEMO=false and SEED_CATALOGUE=true initialize six fictional
  products idempotently without creating shared demo login accounts.
- backend/provision.py creates an admin using private ADMIN_EMAIL/ADMIN_PASSWORD
  variables (minimum 16-character password). Existing customers cannot be
  promoted; existing admin passwords are not reset. Remove bootstrap variables
  after provisioning. No HTTP bootstrap endpoint exists.
- Backend suite: 28 tests passed. Four new provisioning tests also passed in a
  separate run. Frontend lint and production build passed.
- Installed Python/venv works outside sandbox (escalation required). Local Docker
  daemon unavailable: container build/Linux dependency resolution not verified.
- Local HEAD and remote main: c0e7526a06b494e645471f3bf2bd7f60452ac46d.
  Application and deployment changes remain uncommitted. GitHub read access works.

## Remaining deployment work

1. Resolve target project, inspect billing and configure private admin credentials.
2. Review/publish exact local source, excluding secrets, databases and dataset.
3. Configure Docker build, correct start command, persistent database and safe seed
   variables BEFORE triggering deployment; current remote source is old.
4. Inspect build/runtime logs and resolve any Linux dependency issues.
5. Verify HTTPS, actual inference, CSS, registration, orders, reviews, administrator
   authorization and persistence across restart. Record deployment ID and URL.
