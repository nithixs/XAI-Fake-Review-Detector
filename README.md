# ReviewGuard

**AI-Powered Product Review Intelligence and Suspicious Review Detection System**

A complete academic demonstration that connects an e-commerce review workflow to the existing TF-IDF / Logistic Regression classifier and genuine SHAP explanations. React provides the interface; FastAPI serves the API and the built frontend; SQLite makes the demonstration self-contained. MySQL is an optional persistence adapter.

## Run the project

Prerequisites: Python **3.11**, Node.js **22.12+**, and npm. The existing model artifacts are included, so training is **not** required before demonstrating the application.

From the project folder on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Open **http://127.0.0.1:8000**. After setup you can also double-click **start-demo.cmd**. Keep the terminal open while demonstrating. Interactive API documentation is at **http://127.0.0.1:8000/docs**.

Setup installs the recorded Python versions from `requirements-lock.txt` and uses `npm ci`. `requirements.txt` lists the direct dependencies for environments that need to resolve their own versions. Saved scikit-learn models should be used with the recorded library versions.

The first startup creates `database/reviewguard.db`, six fictional products, demo customer orders, and labelled sample reviews analyzed by the real model. Subsequent starts preserve accounts, orders, reviews and moderation decisions. No payment is collected and no physical product is ordered.

| Demo role | Email | Password |
| --- | --- | --- |
| Customer | customer@reviewguard.demo | Demo@12345 |
| Administrator | admin@reviewguard.demo | Admin@12345 |

You can register a fresh customer account to demonstrate the complete flow. Demo credentials are intended for local academic use. `SEED_DEMO=false` stops creation of demo records; existing demo records remain until you choose a fresh database. Do not publish a demo database containing shared admin credentials.

## What is implemented

- Product catalogue with search, categories, product specifications, INR prices, ratings and review counts.
- Customer registration/login, salted password hashes, opaque expiring sessions and logout revocation.
- Simulated purchases and account order history, with server-calculated prices.
- Product-specific star ratings and reviews, with one review per customer per product.
- Verified Purchase derived from a matching completed order, never from a client-provided badge.
- The original standalone analysis lab, ML probabilities, prediction confidence and recent analysis history.
- SHAP word/phrase contributions, positive/negative feature influence and additive explanation diagnostics.
- Rule-based sentiment and aspect sentiment, transparently distinguished from trained ML.
- An explained contextual authenticity score using the text-model result, purchase records, product context and reviewer history.
- Per-product sentiment, rating, suspicious-review and aspect analytics calculated from stored visible reviews.
- Role-protected admin statistics and review inspection, verification, soft removal and restoration, with a moderation audit log.
- A model information screen and reproducible evaluation artifacts; no fabricated accuracy values.

## Understand the AI correctly

The classifier was trained on the supplied dataset's **OR (original)** and **CG (computer-generated)** labels. The interface retains “Genuine” and “Fake / Suspicious” as project labels, but those predictions are estimates of text patterns, **not proof of fraud or honesty**. Original reviews can be deceptive, and generated reviews can describe real experiences.

TF-IDF converts English words and bigrams into numerical features. Logistic Regression outputs class probabilities. SHAP's linear explainer explains the text model in **log-odds units**, not percentage points. Displayed words are a subset of the complete explanation; the API includes the baseline, full contribution sum and reconstruction error.

Sentiment/aspects are a separate English lexicon and negation heuristic. The contextual authenticity score is an explicitly labelled heuristic, not a calibrated probability and not an additional trained classifier. A verified purchase does not prove a truthful review. Inputs with little recognized vocabulary receive an evidence limitation. See [the technical report](docs/PROJECT_REPORT.md) and [demo/viva guide](docs/DEMO_GUIDE.md).

## Development

Run the backend from the project root:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Vite serves the UI at `http://localhost:5173` and proxies `/api` to port 8000. The production build uses the same `/api` URLs through FastAPI. `VITE_API_URL` can be set when building for a separately hosted backend. Restart the backend after rebuilding the frontend if the assets directory did not exist when it started.

## Configuration and existing data

See `.env.example`. The application reads an optional root `.env` without overwriting process environment variables. Your original `.env` is never rewritten. SQLite is the default even if legacy `DB_HOST`/`DB_NAME` values are present. The original MySQL `review_history` is left in place; it is not automatically copied to SQLite.

To use an existing MySQL server, create a database first, then set `DB_ENGINE=mysql`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME`. Tables are created automatically. Existing legacy analysis records remain separate from product reviews because they have no product/customer identity. Automated integration tests use SQLite; the optional MySQL path needs testing against your MySQL server.

For a separate clean demo database without deleting existing records:

```powershell
$env:SQLITE_PATH = 'database/fresh-demo.db'
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

## Verification and model evaluation

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
.\venv\Scripts\python.exe ai_model/evaluate_model.py
```

Backend tests use temporary databases. They verify authorization, session revocation, customer/order isolation, purchase badges, duplicate reviews, input validation, moderation and analytics, plus real ML/SHAP behavior. Frontend checks include ESLint and a production build.

The supplied CSV is at `ai_model/dataset/fake_reviews.csv` (excluded from Git). Evaluation checks compatibility with the original split and reports duplicate overlap/provenance limits. Read `ai_model/saved_model/evaluation_metrics.json` for exact measured results. Do not present a random holdout score as real-world fraud-detection accuracy.

For a new model, run `python ai_model/train_model.py --help` and choose a separate output directory. The upgraded trainer deduplicates before splitting, persists metrics and split metadata, and protects existing artifacts from accidental overwrite. Train on a dataset with verified provenance before claiming broader generalization.

## Submission materials

- [Technical report and architecture](docs/PROJECT_REPORT.md)
- [Demonstration script, viva answers and resume wording](docs/DEMO_GUIDE.md)
- [Verification record](docs/VERIFICATION.md)
- `scripts/package_submission.py` creates a clean source-and-model ZIP without secrets, virtual environments, databases or browser test data.

## Structure

```text
backend/             FastAPI routes, authentication, persistence, AI service, demo seed
frontend/            React UI, responsive styles and local product illustrations
ai_model/            Model artifacts, training and evaluation scripts
database/            Local SQLite data (generated, not committed)
tests/               API, persistence and intelligence tests
scripts/             Setup, launch, verification and packaging
docs/                Submission report and presentation notes
```

This is an academic application with simulated checkout, English-focused text analysis and human moderation. A real commercial deployment would additionally require real payment/order fulfillment, operational monitoring, abuse controls, password recovery, HTTPS deployment and validation on representative real-world review data.
