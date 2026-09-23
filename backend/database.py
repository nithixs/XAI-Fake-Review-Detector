"""SQLite/MySQL persistence. Purchase verification always comes from stored orders."""
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / '.env')
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'reviewguard'),
    'use_pure': True,
}


def _mysql():
    return os.getenv('DB_ENGINE', 'sqlite').lower() == 'mysql'


def get_connection():
    if _mysql():
        import mysql.connector
        return mysql.connector.connect(**DB_CONFIG)
    database_path = Path(os.getenv('SQLITE_PATH', str(PROJECT_ROOT / 'database' / 'reviewguard.db')))
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path), timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute('PRAGMA busy_timeout = 20000')
    return connection


@contextmanager
def _cursor():
    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True) if _mysql() else connection.cursor()
        yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def _execute(cursor, sql, values=()):
    cursor.execute(sql.replace('?', '%s') if _mysql() else sql, values)
    return cursor


def _json_safe(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _row(row):
    return _json_safe(dict(row)) if row is not None else None


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')


def _timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime('%Y-%m-%d %H:%M:%S')


def _is_integrity_error(error):
    return isinstance(error, sqlite3.IntegrityError) or type(error).__name__ == 'IntegrityError'


def create_tables():
    """Idempotent schema creation; never rewrites or deletes legacy history."""
    identity = 'INTEGER PRIMARY KEY AUTO_INCREMENT' if _mysql() else 'INTEGER PRIMARY KEY AUTOINCREMENT'
    statements = [
        f'''CREATE TABLE IF NOT EXISTS review_history (
            id {identity}, review TEXT NOT NULL, prediction VARCHAR(50) NOT NULL,
            confidence REAL NOT NULL, fake_probability REAL NOT NULL,
            genuine_probability REAL NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''',
        f'''CREATE TABLE IF NOT EXISTS app_users (
            id {identity}, name VARCHAR(100) NOT NULL, email VARCHAR(254) NOT NULL UNIQUE,
            password_hash VARCHAR(512) NOT NULL, role VARCHAR(20) NOT NULL DEFAULT 'customer',
            is_demo INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''',
        '''CREATE TABLE IF NOT EXISTS app_sessions (
            token_hash VARCHAR(128) PRIMARY KEY, user_id INTEGER NOT NULL,
            expires_at DATETIME NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE)''',
        f'''CREATE TABLE IF NOT EXISTS products (
            id {identity}, seed_key VARCHAR(100) UNIQUE, name VARCHAR(180) NOT NULL,
            description TEXT NOT NULL, category VARCHAR(80) NOT NULL, price REAL NOT NULL,
            image_key VARCHAR(80) NOT NULL, specifications TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''',
        f'''CREATE TABLE IF NOT EXISTS customer_orders (
            id {identity}, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1, unit_price REAL NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'completed', is_demo INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES app_users(id),
            FOREIGN KEY (product_id) REFERENCES products(id))''',
        f'''CREATE TABLE IF NOT EXISTS product_reviews (
            id {identity}, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5), review TEXT NOT NULL,
            analysis_json TEXT NOT NULL, prediction VARCHAR(50) NOT NULL,
            confidence REAL NOT NULL, fake_probability REAL NOT NULL,
            genuine_probability REAL NOT NULL, sentiment VARCHAR(20) NOT NULL,
            authenticity_score REAL NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'active',
            is_demo INTEGER NOT NULL DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, product_id), FOREIGN KEY (user_id) REFERENCES app_users(id),
            FOREIGN KEY (product_id) REFERENCES products(id))''',
        f'''CREATE TABLE IF NOT EXISTS review_moderation_log (
            id {identity}, review_id INTEGER NOT NULL, admin_id INTEGER NOT NULL,
            previous_status VARCHAR(20) NOT NULL, status VARCHAR(20) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES product_reviews(id),
            FOREIGN KEY (admin_id) REFERENCES app_users(id))''',
    ]
    with _cursor() as cursor:
        for statement in statements:
            _execute(cursor, statement)
        if not _mysql():
            for statement in (
                'CREATE INDEX IF NOT EXISTS idx_review_product_status ON product_reviews(product_id, status)',
                'CREATE INDEX IF NOT EXISTS idx_orders_customer_product ON customer_orders(user_id, product_id, status)',
                'CREATE INDEX IF NOT EXISTS idx_review_user_created ON product_reviews(user_id, created_at)',
                'CREATE INDEX IF NOT EXISTS idx_session_expiry ON app_sessions(expires_at)',
            ):
                _execute(cursor, statement)


def save_review(review, prediction, confidence, fake_probability, genuine_probability):
    with _cursor() as cursor:
        _execute(cursor, '''INSERT INTO review_history
            (review, prediction, confidence, fake_probability, genuine_probability)
            VALUES (?, ?, ?, ?, ?)''', (review, prediction, confidence, fake_probability, genuine_probability))
        return cursor.lastrowid


def get_review_history(limit=20):
    with _cursor() as cursor:
        return [_row(row) for row in _execute(cursor,
            'SELECT * FROM review_history ORDER BY id DESC LIMIT ?', (max(1, min(int(limit), 200)),)).fetchall()]


def get_dashboard_stats():
    with _cursor() as cursor:
        result = _row(_execute(cursor, '''SELECT COUNT(*) AS total_reviews,
            SUM(CASE WHEN fake_probability >= 50 THEN 1 ELSE 0 END) AS fake_reviews,
            SUM(CASE WHEN fake_probability < 50 THEN 1 ELSE 0 END) AS genuine_reviews,
            AVG(confidence) AS average_confidence FROM review_history''').fetchone())
    total = int(result['total_reviews'])
    return {'total_reviews': total, 'fake_reviews': int(result['fake_reviews'] or 0),
            'genuine_reviews': int(result['genuine_reviews'] or 0),
            'average_confidence': round(float(result['average_confidence'] or 0), 2),
            'fake_rate': round(100 * (result['fake_reviews'] or 0) / total, 2) if total else 0}


def _public_user(row):
    user = _row(row)
    if user:
        user.pop('password_hash', None)
        user['is_demo'] = bool(user['is_demo'])
    return user


def create_user(name, email, password_hash, role='customer', *, is_demo=False):
    if role not in ('customer', 'admin'):
        raise ValueError('Invalid user role')
    try:
        with _cursor() as cursor:
            _execute(cursor, '''INSERT INTO app_users (name, email, password_hash, role, is_demo)
                VALUES (?, ?, ?, ?, ?)''', (name.strip(), email.strip().lower(), password_hash, role, int(is_demo)))
            user_id = cursor.lastrowid
    except Exception as error:
        if _is_integrity_error(error):
            raise ValueError('An account with this email already exists') from error
        raise
    return get_user(user_id)


def get_user_by_email(email):
    with _cursor() as cursor:
        return _row(_execute(cursor, 'SELECT * FROM app_users WHERE email = ?', (email.strip().lower(),)).fetchone())


def get_user(user_id):
    with _cursor() as cursor:
        return _public_user(_execute(cursor, 'SELECT * FROM app_users WHERE id = ?', (user_id,)).fetchone())


def create_session(user_id, token_hash, expires_at):
    with _cursor() as cursor:
        _execute(cursor, 'DELETE FROM app_sessions WHERE expires_at <= ?', (_now(),))
        _execute(cursor, 'INSERT INTO app_sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)',
                 (user_id, token_hash, _timestamp(expires_at)))


def get_session_user(token_hash):
    with _cursor() as cursor:
        return _public_user(_execute(cursor, '''SELECT u.* FROM app_sessions s
            JOIN app_users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?''',
            (token_hash, _now())).fetchone())


def delete_session(token_hash):
    with _cursor() as cursor:
        _execute(cursor, 'DELETE FROM app_sessions WHERE token_hash = ?', (token_hash,))


_PRODUCT_SELECT = '''SELECT p.*,
    COALESCE(AVG(r.rating), 0) AS average_rating, COUNT(r.id) AS total_reviews,
    COALESCE(SUM(CASE WHEN r.fake_probability >= 50 THEN 1 ELSE 0 END), 0) AS suspicious_reviews
    FROM products p LEFT JOIN product_reviews r ON r.product_id = p.id AND r.status != 'removed' '''


def _product(row):
    product = _row(row)
    if product:
        product['price'] = round(float(product['price']), 2)
        product['average_rating'] = round(float(product['average_rating'] or 0), 1)
        product['total_reviews'] = int(product['total_reviews'])
        product['suspicious_reviews'] = int(product['suspicious_reviews'])
        product['is_demo'] = bool(product['is_demo'])
        product['specifications'] = json.loads(product['specifications'])
    return product


def list_products(search='', category=''):
    filters, parameters = [], []
    if search:
        filters.append('(LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ?)')
        parameters.extend([f'%{search.lower()}%'] * 2)
    if category and category.lower() != 'all':
        filters.append('LOWER(p.category) = ?')
        parameters.append(category.lower())
    where = ' WHERE ' + ' AND '.join(filters) if filters else ''
    with _cursor() as cursor:
        return [_product(row) for row in _execute(cursor,
            _PRODUCT_SELECT + where + ' GROUP BY p.id ORDER BY p.id', tuple(parameters)).fetchall()]


def get_product(product_id):
    with _cursor() as cursor:
        return _product(_execute(cursor, _PRODUCT_SELECT + ' WHERE p.id = ? GROUP BY p.id', (product_id,)).fetchone())


def create_order(user_id, product_id, quantity=1):
    """Create a completed simulation purchase. No money is collected."""
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1 or quantity > 10:
        raise ValueError('Quantity must be between 1 and 10')
    with _cursor() as cursor:
        product = _row(_execute(cursor, 'SELECT id, price FROM products WHERE id = ?', (product_id,)).fetchone())
        if not product:
            raise ValueError('Product not found')
        if not _execute(cursor, 'SELECT id FROM app_users WHERE id = ?', (user_id,)).fetchone():
            raise ValueError('Customer not found')
        _execute(cursor, '''INSERT INTO customer_orders (user_id, product_id, quantity, unit_price, status, is_demo)
            VALUES (?, ?, ?, ?, 'completed', 1)''', (user_id, product_id, quantity, product['price']))
        order_id = cursor.lastrowid
    return next(order for order in get_orders(user_id) if order['id'] == order_id)


def get_orders(user_id):
    with _cursor() as cursor:
        orders = [_row(row) for row in _execute(cursor, '''SELECT o.*, p.name AS product_name,
            p.image_key, p.category FROM customer_orders o JOIN products p ON p.id = o.product_id
            WHERE o.user_id = ? ORDER BY o.id DESC''', (user_id,)).fetchall()]
    for order in orders:
        order['is_demo'] = bool(order['is_demo'])
        order['unit_price'] = float(order['unit_price'])
        order['total'] = round(order['unit_price'] * order['quantity'], 2)
        order['total_amount'] = order['total']
        order['order_number'] = f"RG-{order['id']:05d}"
    return orders


def has_purchase(user_id, product_id):
    with _cursor() as cursor:
        return _execute(cursor, '''SELECT id FROM customer_orders
            WHERE user_id = ? AND product_id = ? AND status = 'completed' LIMIT 1''',
            (user_id, product_id)).fetchone() is not None


def user_review_context(user_id, review):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
    with _cursor() as cursor:
        rows = [_row(row) for row in _execute(cursor,
            'SELECT review, created_at FROM product_reviews WHERE user_id = ?', (user_id,)).fetchall()]
    normalized = ' '.join(review.lower().split())
    return {'review_count': len(rows),
            'recent_review_count': sum(str(row['created_at']) >= cutoff for row in rows),
            'duplicate_count': sum(' '.join(row['review'].lower().split()) == normalized for row in rows)}


_REVIEW_SELECT = '''SELECT r.*, u.name AS user_name, p.name AS product_name, p.image_key,
    EXISTS (SELECT 1 FROM customer_orders o WHERE o.user_id = r.user_id
            AND o.product_id = r.product_id AND o.status = 'completed') AS verified_purchase
    FROM product_reviews r JOIN app_users u ON u.id = r.user_id JOIN products p ON p.id = r.product_id '''


def _review(row):
    review = _row(row)
    if review:
        review['analysis'] = json.loads(review.pop('analysis_json'))
        review['verified_purchase'] = bool(review['verified_purchase'])
        review['is_demo'] = bool(review['is_demo'])
        review['customer_name'] = review['user_name']
        review['moderation_status'] = review['status']
        review['aspects'] = review['analysis'].get('aspects', [])
        for field in ('confidence', 'fake_probability', 'genuine_probability', 'authenticity_score'):
            review[field] = float(review[field])
    return review


def create_product_review(user_id, product_id, rating, review, analysis, *, is_demo=False, created_at=None):
    if not isinstance(rating, int) or isinstance(rating, bool) or rating not in range(1, 6):
        raise ValueError('Rating must be between 1 and 5')
    if not review.strip():
        raise ValueError('Review cannot be empty')
    sentiment = analysis.get('sentiment', 'Neutral')
    if isinstance(sentiment, dict):
        sentiment = sentiment.get('label', 'Neutral')
    fake_probability = float(analysis.get('fake_probability', 0))
    try:
        with _cursor() as cursor:
            if not _execute(cursor, 'SELECT id FROM products WHERE id = ?', (product_id,)).fetchone():
                raise ValueError('Product not found')
            if not _execute(cursor, 'SELECT id FROM app_users WHERE id = ?', (user_id,)).fetchone():
                raise ValueError('Customer not found')
            _execute(cursor, '''INSERT INTO product_reviews
                (user_id, product_id, rating, review, analysis_json, prediction, confidence,
                 fake_probability, genuine_probability, sentiment, authenticity_score, is_demo, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (user_id, product_id, rating, review.strip(), json.dumps(_json_safe(analysis)),
                 analysis.get('prediction', 'Genuine'), float(analysis.get('confidence', 0)),
                 fake_probability, float(analysis.get('genuine_probability', 100 - fake_probability)),
                 str(sentiment).title(), float(analysis.get('authenticity_score', 100 - fake_probability)),
                 int(is_demo), _timestamp(created_at) if created_at else _now(), _now()))
            review_id = cursor.lastrowid
    except Exception as error:
        if _is_integrity_error(error):
            raise ValueError('You have already reviewed this product') from error
        raise
    return get_product_review(review_id)


def get_product_review(review_id):
    with _cursor() as cursor:
        return _review(_execute(cursor, _REVIEW_SELECT + ' WHERE r.id = ?', (review_id,)).fetchone())


def list_product_reviews(product_id):
    with _cursor() as cursor:
        return [_review(row) for row in _execute(cursor,
            _REVIEW_SELECT + " WHERE r.product_id = ? AND r.status != 'removed' ORDER BY r.created_at DESC, r.id DESC",
            (product_id,)).fetchall()]


def get_user_reviews(user_id):
    with _cursor() as cursor:
        return [_review(row) for row in _execute(cursor,
            _REVIEW_SELECT + ' WHERE r.user_id = ? ORDER BY r.id DESC', (user_id,)).fetchall()]


def get_product_analytics(product_id):
    product = get_product(product_id)
    if product is None:
        return None
    reviews = list_product_reviews(product_id)
    total = len(reviews)
    sentiments = Counter(review['sentiment'] for review in reviews)
    ratings = Counter(str(review['rating']) for review in reviews)
    aspect_counts = defaultdict(Counter)
    for review in reviews:
        aspects = review.get('aspects', [])
        if isinstance(aspects, dict):
            aspects = [{'aspect': name, 'sentiment': value} for name, value in aspects.items()]
        for item in aspects:
            if isinstance(item, dict):
                name = str(item.get('aspect', item.get('name', 'Other')))
                label = item.get('sentiment', 'Neutral')
                if isinstance(label, dict):
                    label = label.get('label', 'Neutral')
                aspect_counts[name][str(label).title()] += 1
    aspect_summary = [{'aspect': name, 'positive': counts['Positive'], 'neutral': counts['Neutral'],
                       'negative': counts['Negative'], 'total': sum(counts.values())}
                      for name, counts in sorted(aspect_counts.items())]
    liked = sorted([{'aspect': name, 'count': counts['Positive']} for name, counts in aspect_counts.items()
                    if counts['Positive']], key=lambda item: (-item['count'], item['aspect']))
    disliked = sorted([{'aspect': name, 'count': counts['Negative']} for name, counts in aspect_counts.items()
                       if counts['Negative']], key=lambda item: (-item['count'], item['aspect']))
    percentages = {label: round(sentiments[label] * 100 / total, 1) if total else 0
                   for label in ('Positive', 'Neutral', 'Negative')}
    suspicious = sum(review['fake_probability'] >= 50 for review in reviews)
    return {'product': product, 'product_id': product_id, 'product_name': product['name'],
            'total_reviews': total, 'average_rating': product['average_rating'],
            'suspicious_reviews': suspicious, 'genuine_reviews': total - suspicious,
            'verified_purchases': sum(review['verified_purchase'] for review in reviews),
            'average_authenticity': round(sum(review['authenticity_score'] for review in reviews) / total, 1) if total else 0,
            'sentiment_counts': {label: sentiments[label] for label in percentages},
            'sentiment_percentages': percentages,
            'sentiment': {label: {'count': sentiments[label], 'percentage': percentages[label]} for label in percentages},
            'rating_distribution': {str(star): ratings[str(star)] for star in range(1, 6)},
            'aspects': aspect_summary, 'liked_aspects': liked, 'disliked_aspects': disliked,
            'customers_like': [item['aspect'] for item in liked],
            'customers_dislike': [item['aspect'] for item in disliked]}


def list_admin_reviews(status='all'):
    filters, values = [], []
    if status in ('active', 'verified', 'removed'):
        filters.append('r.status = ?')
        values.append(status)
    elif status == 'suspicious':
        filters.append("r.fake_probability >= 50 AND r.status != 'removed'")
    elif status == 'genuine':
        filters.append("r.fake_probability < 50 AND r.status != 'removed'")
    elif status != 'all':
        raise ValueError('Invalid review filter')
    where = ' WHERE ' + ' AND '.join(filters) if filters else ''
    with _cursor() as cursor:
        return [_review(row) for row in _execute(cursor,
            _REVIEW_SELECT + where + ' ORDER BY r.created_at DESC, r.id DESC', tuple(values)).fetchall()]


def get_admin_stats():
    with _cursor() as cursor:
        users = _row(_execute(cursor, "SELECT COUNT(*) AS total FROM app_users WHERE role = 'customer'").fetchone())['total']
        orders = _row(_execute(cursor, 'SELECT COUNT(*) AS total FROM customer_orders').fetchone())['total']
        complaint = _row(_execute(cursor, '''SELECT p.id, p.name, COUNT(r.id) AS negative_reviews
            FROM products p JOIN product_reviews r ON r.product_id = p.id
            WHERE r.status != 'removed' AND r.sentiment = 'Negative'
            GROUP BY p.id ORDER BY negative_reviews DESC, p.id LIMIT 1''').fetchone())
    products = list_products()
    reviews = list_admin_reviews()
    visible = [review for review in reviews if review['status'] != 'removed']
    most = max(products, key=lambda product: product['total_reviews'], default=None)
    most = {'id': most['id'], 'name': most['name'], 'total_reviews': most['total_reviews']} if most and most['total_reviews'] else None
    suspicious = sum(review['fake_probability'] >= 50 for review in visible)
    return {'total_products': len(products), 'total_customers': int(users), 'total_orders': int(orders),
            'total_reviews': len(visible), 'all_reviews': len(reviews),
            'genuine_reviews': len(visible) - suspicious, 'suspicious_reviews': suspicious,
            'fake_reviews': suspicious, 'removed_reviews': sum(review['status'] == 'removed' for review in reviews),
            'verified_reviews': sum(review['status'] == 'verified' for review in visible),
            'verified_purchases': sum(review['verified_purchase'] for review in visible),
            'most_reviewed_product': most, 'most_complained_product': complaint,
            'average_confidence': round(sum(review['confidence'] for review in visible) / len(visible), 2) if visible else 0,
            'suspicious_rate': round(suspicious * 100 / len(visible), 1) if visible else 0}


def moderate_review(review_id, status, admin_id):
    """Soft moderation with an audit trail. Human verification is not a purchase."""
    if status not in ('verified', 'removed', 'active'):
        raise ValueError('Invalid moderation status')
    with _cursor() as cursor:
        admin = _row(_execute(cursor, 'SELECT role FROM app_users WHERE id = ?', (admin_id,)).fetchone())
        if not admin or admin['role'] != 'admin':
            raise PermissionError('Administrator access required')
        review = _row(_execute(cursor, 'SELECT status FROM product_reviews WHERE id = ?', (review_id,)).fetchone())
        if not review:
            raise ValueError('Review not found')
        if review['status'] != status:
            _execute(cursor, 'UPDATE product_reviews SET status = ?, updated_at = ? WHERE id = ?', (status, _now(), review_id))
            _execute(cursor, '''INSERT INTO review_moderation_log (review_id, admin_id, previous_status, status)
                VALUES (?, ?, ?, ?)''', (review_id, admin_id, review['status'], status))
    return get_product_review(review_id)


def seed_demo(analyze_fn, hash_password):
    from backend.seed import seed_demo as seed
    return seed(analyze_fn, hash_password)
