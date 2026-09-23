# Verification record

## Current local verification

| Check | Result | Evidence |
| --- | --- | --- |
| Frontend lint | Passed | `npm.cmd run lint` completed successfully on 22 September 2026. |
| Frontend production build | Passed | `npm.cmd run build` completed successfully on 22 September 2026 and generated `frontend/dist/`. |
| Backend automated tests | Pending local Python repair | The checked-in virtual environment points to a removed Python 3.11 installation. `scripts/setup.ps1` now detects and rebuilds this environment once Python 3.11 is installed. |

## Required final check before submission

### UI stylesheet correction

The React workspace used new class names while importing the legacy prototype
stylesheet. `frontend/src/App.jsx` now imports `reviewguard.css`, which styles
the current catalogue, navigation, product reviews, analytics, analysis lab,
authentication, accounts, moderation, and methodology screens, with responsive
breakpoints and keyboard focus states.

Frontend lint and production build passed after this correction. The generated
CSS was checked for the main screen selectors (`.app-shell`, `.sidebar`,
`.hero-banner`, `.product-grid`, `.auth-layout`, `.feature-row`, and
`.moderation-list`). The launcher now rebuilds when frontend inputs are newer
than the existing build. A rendered browser walkthrough remains unverified:
no browser was connected to this session, and the backend was unreachable.

On the presentation computer, with Python 3.11 and Node.js installed, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Then open `http://127.0.0.1:8000` and complete the seven-minute walkthrough in `docs/DEMO_GUIDE.md`. The backend test suite uses temporary SQLite databases, so it does not alter the main demo database.

## Expected automated coverage

`tests/` covers registration, login/logout, session expiry, role authorization, order ownership, server-side price calculation, purchase verification, duplicate reviews, input validation, moderation audit/removal/restoration, analytics consistency, real model probability handling, SHAP additivity, unknown-vocabulary disclosure, and sentiment/aspect rule behavior.
