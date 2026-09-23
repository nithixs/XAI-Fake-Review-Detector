# ReviewGuard demonstration and viva guide

## Before the presentation

Run setup once while you have internet access, then run `start-demo.cmd`. Open `http://127.0.0.1:8000`. The runtime uses local model files, local product graphics and a local database; it does not call a paid AI API. Keep the API terminal open. Use the same browser tab during the presentation because authentication is kept in session storage.

If you want a clean presentation without deleting previous work, set `SQLITE_PATH=database/presentation.db` before starting. Demo seeding is idempotent and does not reset existing accounts or moderation decisions.

## Seven-minute demonstration

1. **Problem (30 seconds).** “A review classifier needs product and transaction context. This system connects explainable ML to a complete customer-review workflow.”
2. **Catalogue (45 seconds).** Search or filter products. Open Aura Wireless Headphones. Show the price, specifications, computed rating and sample customer reviews. Point out demo-record labels.
3. **Customer and purchase (60 seconds).** Register a new account. Place a demo purchase. Explain that no money is charged and that the completed order is persisted. Open the account order history.
4. **Product review and XAI (90 seconds).** Give four stars and submit: “I used these headphones for two weeks. The sound is clear and the cushions are comfortable, but the battery life is poor.” Show the Verified Purchase badge, raw ML probabilities, sentiment/aspects and the SHAP feature chart. Do not promise a particular prediction: the displayed result comes from the actual saved model.
5. **Unverified review (45 seconds).** Open another product and write a review without buying it. Show that it has no purchase verification. Explain that unverified does not automatically mean fake.
6. **Product analytics (45 seconds).** Show the review count, rating distribution, sentiment chart and liked/disliked aspects. These change when a review is submitted or moderated.
7. **Administration (60 seconds).** Sign out and sign in as `admin@reviewguard.demo` / `Admin@12345`. Inspect a review's analysis, verify it, remove it, then restore it. Explain that human verification is different from a purchase badge and that removal is reversible.
8. **Model evidence (45 seconds).** Open the model/method information view. Mention the real feature count, evaluation metrics and the generated-text proxy limitation. End by showing `/docs` and the automated-test results.

## Questions you should be able to answer

**Where is the machine learning?** TF-IDF transforms text and a trained Logistic Regression classifier produces probabilities for the original/generated label task. The stored trained artifacts are used at runtime.

**Where is explainable AI?** SHAP LinearExplainer assigns feature contributions relative to a background expectation. Contributions add to model log-odds. A highlighted word is a model association, not proof of deception.

**Why Logistic Regression instead of a large language model?** It is lightweight, runs locally, supports reproducible training and is easy to inspect with a linear explainer. The project does not require a paid API or internet during inference.

**Is sentiment another ML model?** No. Sentiment and aspects are an explicitly disclosed rule-based layer. They are separate from the trained authenticity text classifier.

**Is the authenticity score the ML probability?** No. Raw class probabilities are retained. The contextual score applies transparent signals from purchase status, product information and reviewer history, so it must not be interpreted as a calibrated probability.

**How do you prevent fake purchase badges?** The API queries completed orders for the authenticated customer and product. The client cannot submit a trusted purchase flag or another customer's ID.

**Can a customer call an admin API manually?** The server checks their authenticated role. Hiding the admin navigation alone would not be sufficient.

**Can an admin's verification prove a purchase?** No. It is a separate moderation state. Only a matching completed order controls the purchase badge.

**How is accuracy measured?** Use the exact metrics JSON and explain its split, label definitions, duplicate audit and provenance qualifications. Do not claim that generated-text classification accuracy equals real-world fake-review detection accuracy.

**What happens with Tamil or unseen vocabulary?** The English-focused model may have insufficient recognized features. The application reports this limitation; multilingual learning is future work.

**What is original about this project?** The application integrates explainable text classification, transaction-based verification, reviewer context, product analytics and auditable moderation in one workflow. Avoid claiming that TF-IDF, Logistic Regression or SHAP were invented for this project.

**What would you improve next?** Independently labelled deceptive-review data, multilingual support, calibration, real order verification, reviewer network analysis and deployment hardening.

## Resume wording

**ReviewGuard — Explainable Product Review Intelligence**

- Built a React/FastAPI review platform with customer accounts, simulated purchases, transaction-derived verification and role-based moderation.
- Integrated TF-IDF and Logistic Regression inference with SHAP feature explanations and reproducible evaluation on the supplied labelled review dataset.
- Implemented product sentiment/aspect dashboards, contextual review signals, persistent audit history and automated integration tests.

Add numerical metrics only after checking `evaluation_metrics.json`, and identify the task as original-versus-generated review classification. Be prepared to explain and run every feature you list.
