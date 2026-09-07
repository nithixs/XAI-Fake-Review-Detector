import os
import mysql.connector
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

load_dotenv(
    os.path.join(PROJECT_ROOT, ".env"),
    override=True
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME"),
    "use_pure": True
}


def get_connection():
    return mysql.connector.connect(
        **DB_CONFIG
    )


def save_review(
    review,
    prediction,
    confidence,
    fake_probability,
    genuine_probability
):
    connection = get_connection()
    cursor = connection.cursor()

    query = """
        INSERT INTO review_history
        (
            review,
            prediction,
            confidence,
            fake_probability,
            genuine_probability
        )
        VALUES (%s, %s, %s, %s, %s)
    """

    values = (
        review,
        prediction,
        confidence,
        fake_probability,
        genuine_probability
    )

    cursor.execute(query, values)
    connection.commit()

    cursor.close()
    connection.close()


def get_review_history(limit=20):
    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT
            id,
            review,
            prediction,
            confidence,
            fake_probability,
            genuine_probability,
            created_at
        FROM review_history
        ORDER BY id DESC
        LIMIT %s
    """

    cursor.execute(
        query,
        (limit,)
    )

    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    for row in rows:
        row["confidence"] = float(
            row["confidence"]
        )

        row["fake_probability"] = float(
            row["fake_probability"]
        )

        row["genuine_probability"] = float(
            row["genuine_probability"]
        )

        row["created_at"] = (
            row["created_at"]
            .strftime("%Y-%m-%d %H:%M:%S")
        )

    return rows


def get_dashboard_stats():
    connection = get_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    query = """
        SELECT
            COUNT(*) AS total_reviews,

            SUM(
                CASE
                    WHEN prediction LIKE 'Fake%'
                    THEN 1
                    ELSE 0
                END
            ) AS fake_reviews,

            SUM(
                CASE
                    WHEN prediction = 'Genuine'
                    THEN 1
                    ELSE 0
                END
            ) AS genuine_reviews,

            AVG(confidence)
            AS average_confidence

        FROM review_history
    """

    cursor.execute(query)

    stats = cursor.fetchone()

    cursor.close()
    connection.close()

    total = stats["total_reviews"] or 0
    fake = stats["fake_reviews"] or 0
    genuine = stats["genuine_reviews"] or 0

    average = (
        float(stats["average_confidence"])
        if stats["average_confidence"]
        else 0
    )

    fake_rate = (
        (fake / total) * 100
        if total > 0
        else 0
    )

    return {
        "total_reviews": total,
        "fake_reviews": fake,
        "genuine_reviews": genuine,
        "average_confidence": round(
            average,
            2
        ),
        "fake_rate": round(
            fake_rate,
            2
        )
    }