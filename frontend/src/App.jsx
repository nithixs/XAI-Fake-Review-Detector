import { useEffect, useState } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [review, setReview] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [stats, setStats] = useState({
    total_reviews: 0,
    fake_reviews: 0,
    genuine_reviews: 0,
    average_confidence: 0,
    fake_rate: 0,
  });

  const [history, setHistory] = useState([]);

  // --------------------------------------------------
  // Load Dashboard Stats + Review History
  // --------------------------------------------------

  const loadDashboard = async () => {
    try {
      const [statsResponse, historyResponse] = await Promise.all([
        axios.get("http://127.0.0.1:8000/stats"),
        axios.get("http://127.0.0.1:8000/history"),
      ]);

      setStats(statsResponse.data);
      setHistory(historyResponse.data);
    } catch (err) {
      console.error("Dashboard loading error:", err);
    }
  };

  // --------------------------------------------------
  // Load dashboard when page opens
  // --------------------------------------------------

  useEffect(() => {
    loadDashboard();
  }, []);

  // --------------------------------------------------
  // Analyze Review
  // --------------------------------------------------

  const analyzeReview = async () => {
    if (!review.trim()) {
      setError("Please enter a product review.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const response = await axios.post(
        "http://127.0.0.1:8000/predict",
        {
          review: review,
        }
      );

      setResult(response.data);

      // Refresh dashboard after DB save
      await loadDashboard();
    } catch (err) {
      console.error(err);

      setError(
        "Unable to connect to the AI backend. Make sure FastAPI and MySQL are running."
      );
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------
  // Clear
  // --------------------------------------------------

  const clearReview = () => {
    setReview("");
    setResult(null);
    setError("");
  };

  return (
    <div className="app">
      {/* ------------------------------------------------
          NAVBAR
      ------------------------------------------------ */}

      <header className="navbar">
        <div>
          <h2>XAI ReviewGuard</h2>
          <span>Explainable AI Review Detection</span>
        </div>

        <div className="model-badge">
          TF-IDF + Logistic Regression + SHAP
        </div>
      </header>

      <main className="container">
        {/* ------------------------------------------------
            HERO
        ------------------------------------------------ */}

        <section className="hero">
          <div className="ai-label">EXPLAINABLE AI</div>

          <h1>
            Detect suspicious reviews.
            <br />
            Understand <span>why.</span>
          </h1>

          <p>
            Analyze product reviews using machine learning and SHAP
            explanations to understand the features influencing every
            prediction.
          </p>
        </section>

        {/* ------------------------------------------------
            DASHBOARD
        ------------------------------------------------ */}

        <section className="dashboard">
          <div className="stat-card">
            <p>Total Reviews</p>
            <h2>{stats.total_reviews}</h2>
          </div>

          <div className="stat-card fake-stat">
            <p>Suspicious Reviews</p>
            <h2>{stats.fake_reviews}</h2>
          </div>

          <div className="stat-card genuine-stat">
            <p>Genuine Reviews</p>
            <h2>{stats.genuine_reviews}</h2>
          </div>

          <div className="stat-card">
            <p>Average Confidence</p>
            <h2>{stats.average_confidence}%</h2>
          </div>
        </section>

        {/* ------------------------------------------------
            ANALYZER
        ------------------------------------------------ */}

        <section className="analyzer-card">
          <div className="card-header">
            <div>
              <h3>Analyze Review</h3>
              <p>Paste a product review below.</p>
            </div>

            <span className="character-count">
              {review.length} characters
            </span>
          </div>

          <textarea
            value={review}
            onChange={(e) => setReview(e.target.value)}
            placeholder="Example: I absolutely love this product and the quality is excellent..."
          />

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <div className="button-row">
            <button
              className="analyze-button"
              onClick={analyzeReview}
              disabled={loading}
            >
              {loading
                ? "Analyzing..."
                : "Analyze Review"}
            </button>

            <button
              className="clear-button"
              onClick={clearReview}
            >
              Clear
            </button>
          </div>
        </section>

        {/* ------------------------------------------------
            PREDICTION RESULT
        ------------------------------------------------ */}

        {result && (
          <section className="results">
            {/* Prediction */}

            <div
              className={`prediction-card ${
                result.prediction
                  .toLowerCase()
                  .includes("fake")
                  ? "fake-card"
                  : "genuine-card"
              }`}
            >
              <p className="small-title">
                AI PREDICTION
              </p>

              <h2>{result.prediction}</h2>

              <div className="confidence">
                <strong>
                  {result.confidence}%
                </strong>

                <span>
                  confidence
                </span>
              </div>
            </div>

            {/* Probability */}

            <div className="probability-card">
              <h3>Prediction Probability</h3>

              <div className="probability-item">
                <div className="probability-heading">
                  <span>
                    Suspicious / Fake
                  </span>

                  <strong>
                    {result.fake_probability}%
                  </strong>
                </div>

                <div className="progress-track">
                  <div
                    className="progress-fill fake-progress"
                    style={{
                      width: `${result.fake_probability}%`,
                    }}
                  />
                </div>
              </div>

              <div className="probability-item">
                <div className="probability-heading">
                  <span>
                    Original / Genuine
                  </span>

                  <strong>
                    {result.genuine_probability}%
                  </strong>
                </div>

                <div className="progress-track">
                  <div
                    className="progress-fill genuine-progress"
                    style={{
                      width: `${result.genuine_probability}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* SHAP Explanation */}

            <div className="explanation-card">
              <div className="explanation-heading">
                <div>
                  <p className="small-title">
                    SHAP EXPLANATION
                  </p>

                  <h3>
                    Why did the AI make this prediction?
                  </h3>
                </div>

                <span className="xai-badge">
                  Explainable AI
                </span>
              </div>

              <p className="explanation-note">
                Positive SHAP values push the prediction toward
                Suspicious. Negative SHAP values push it toward
                Genuine.
              </p>

              <div className="feature-table">
                <div className="table-header">
                  <span>Feature</span>
                  <span>Influence</span>
                  <span>SHAP Value</span>
                </div>

                {result.explanation &&
                  result.explanation.map(
                    (item, index) => (
                      <div
                        className="feature-row"
                        key={index}
                      >
                        <strong>
                          "{item.feature}"
                        </strong>

                        <span
                          className={
                            item.influence === "Fake"
                              ? "fake-label"
                              : "genuine-label"
                          }
                        >
                          {item.influence}
                        </span>

                        <span>
                          {item.shap_value > 0
                            ? "+"
                            : ""}
                          {item.shap_value}
                        </span>
                      </div>
                    )
                  )}
              </div>
            </div>
          </section>
        )}

        {/* ------------------------------------------------
            REVIEW HISTORY
        ------------------------------------------------ */}

        <section className="history-card">
          <div className="history-header">
            <div>
              <p className="small-title">
                DATABASE HISTORY
              </p>

              <h3>
                Recent Review Analysis
              </h3>
            </div>

            <span>
              Last {history.length} reviews
            </span>
          </div>

          {history.length === 0 ? (
            <p className="empty-history">
              No reviews analyzed yet.
            </p>
          ) : (
            <div className="history-table">
              <div className="history-row history-title">
                <span>Review</span>
                <span>Prediction</span>
                <span>Confidence</span>
                <span>Date</span>
              </div>

              {history.map((item) => (
                <div
                  className="history-row"
                  key={item.id}
                >
                  <span className="review-preview">
                    {item.review.length > 55
                      ? `${item.review.substring(
                          0,
                          55
                        )}...`
                      : item.review}
                  </span>

                  <span
                    className={
                      item.prediction
                        .toLowerCase()
                        .includes("fake")
                        ? "fake-label"
                        : "genuine-label"
                    }
                  >
                    {item.prediction}
                  </span>

                  <span>
                    {item.confidence}%
                  </span>

                  <span>
                    {item.created_at}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      {/* ------------------------------------------------
          FOOTER
      ------------------------------------------------ */}

      <footer>
        XAI ReviewGuard • Explainable AI-Based Fake Review Detection
      </footer>
    </div>
  );
}

export default App;