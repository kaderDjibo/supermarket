import os
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import io
import hashlib

# ML imports
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import IsolationForest
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "supermarket.db")


# ========== DB CONNECTION & INIT ==========

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # STORES (branches / locations)
    c.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        phone TEXT
    )
    """)

    # Ensure at least one default store
    c.execute("SELECT COUNT(*) FROM stores")
    count = c.fetchone()[0]
    if count == 0:
        c.execute(
            "INSERT INTO stores (name, address, phone) VALUES (?, ?, ?)",
            ("Main Store", "", "")
        )

    # CATEGORIES (optional, minimal)
    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT
    )
    """)

    # PRODUCTS (no stock column here)
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        barcode TEXT UNIQUE,
        price REAL,
        reorder_level INTEGER DEFAULT 5,
        is_active INTEGER DEFAULT 1
    )
    """)

    # STOCK LEVELS (per store)
    c.execute("""
    CREATE TABLE IF NOT EXISTS stock_levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER,
        product_id INTEGER,
        quantity INTEGER DEFAULT 0,
        UNIQUE(store_id, product_id),
        FOREIGN KEY(store_id) REFERENCES stores(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)

    # CUSTOMERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        credit_limit REAL DEFAULT 0.0,
        balance REAL DEFAULT 0.0,
        created_at TEXT
    )
    """)

    # LOAN TRANSACTIONS (store credit history)
    c.execute("""
    CREATE TABLE IF NOT EXISTS loan_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        timestamp TEXT,
        type TEXT,
        amount REAL,
        note TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )
    """)

    # USERS (staff)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT,
        store_id INTEGER,
        FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    # SALES (header)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        store_id INTEGER,
        customer_id INTEGER,
        channel TEXT,
        subtotal REAL,
        discount REAL,
        tax REAL,
        total REAL,
        payment_method TEXT,
        status TEXT DEFAULT 'Completed',
        FOREIGN KEY(store_id) REFERENCES stores(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )
    """)

    # SALE ITEMS (lines)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        product_id INTEGER,
        qty INTEGER,
        unit_price REAL,
        line_total REAL,
        FOREIGN KEY(sale_id) REFERENCES sales(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)

    # SUPPLIERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        contact_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        notes TEXT
    )
    """)

    # PRODUCT-SUPPLIER LINK
    c.execute("""
    CREATE TABLE IF NOT EXISTS product_suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        supplier_id INTEGER,
        is_primary INTEGER DEFAULT 1,
        UNIQUE(product_id, supplier_id),
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
    )
    """)

    # PURCHASE ORDERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        store_id INTEGER,
        timestamp TEXT,
        status TEXT,
        total_amount REAL,
        FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
        FOREIGN KEY(store_id) REFERENCES stores(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_order_id INTEGER,
        product_id INTEGER,
        qty INTEGER,
        unit_cost REAL,
        line_total REAL,
        FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)

    # Ensure at least one admin user
    c.execute("SELECT COUNT(*) FROM users")
    u_count = c.fetchone()[0]
    if u_count == 0:
        # default admin / admin123
        pwd = "admin123"
        pwd_hash = hashlib.sha256(pwd.encode("utf-8")).hexdigest()
        c.execute(
            """
            INSERT INTO users (name, username, password_hash, role, store_id)
            VALUES (?, ?, ?, ?, NULL)
            """,
            ("Admin", "admin", pwd_hash, "admin"),
        )

    conn.commit()
    conn.close()

def get_default_store_id():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM stores ORDER BY id LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_stores():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stores", conn)
    conn.close()
    return df


def get_stock(store_id, product_id):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT quantity FROM stock_levels WHERE store_id = ? AND product_id = ?",
        conn,
        params=(store_id, product_id),
    )
    conn.close()
    if df.empty:
        return 0
    return int(df.iloc[0]["quantity"])


def set_stock(store_id, product_id, quantity):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO stock_levels (store_id, product_id, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(store_id, product_id)
        DO UPDATE SET quantity = excluded.quantity
        """,
        (store_id, product_id, quantity),
    )
    conn.commit()
    conn.close()


def change_stock(store_id, product_id, delta_qty):
    current = get_stock(store_id, product_id)
    new_qty = current + delta_qty
    if new_qty < 0:
        new_qty = 0
    set_stock(store_id, product_id, new_qty)


def update_stock_after_sale(store_id, product_id, qty_sold):
    change_stock(store_id, product_id, -qty_sold)


def get_inventory_for_store(store_id):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT p.id, p.name, p.barcode, p.price, p.reorder_level,
               sl.quantity AS stock
        FROM products p
        JOIN stock_levels sl
            ON p.id = sl.product_id
        WHERE sl.store_id = ?
        ORDER BY p.name
        """,
        conn,
        params=(store_id,),
    )
    conn.close()
    return df


def get_low_stock_products_for_store(store_id):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT p.id, p.name, p.reorder_level,
               sl.quantity AS stock
        FROM products p
        JOIN stock_levels sl
            ON p.id = sl.product_id
        WHERE sl.store_id = ?
          AND sl.quantity <= p.reorder_level
        ORDER BY sl.quantity ASC
        """,
        conn,
        params=(store_id,),
    )
    conn.close()
    return df


# ========== PRODUCT HELPERS ==========

def get_all_products():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM products WHERE is_active = 1", conn)
    conn.close()
    return df


def get_product_by_barcode(barcode):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM products WHERE barcode = ?", conn, params=(barcode,)
    )
    conn.close()
    return df.iloc[0] if not df.empty else None


def get_product_by_id(pid):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM products WHERE id = ?", conn, params=(pid,)
    )
    conn.close()
    return df.iloc[0] if not df.empty else None


# ========== CUSTOMER & LOAN HELPERS ==========

def get_all_customers():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM customers", conn)
    conn.close()
    return df


def create_customer(name, phone, credit_limit):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO customers (name, phone, credit_limit, balance, created_at)
        VALUES (?, ?, ?, 0.0, ?)
        """,
        (name, phone, credit_limit, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_customer_by_id(cid):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM customers WHERE id = ?", conn, params=(cid,)
    )
    conn.close()
    return df.iloc[0] if not df.empty else None


def update_customer_balance(customer_id, new_balance):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE customers SET balance = ? WHERE id = ?",
        (new_balance, customer_id),
    )
    conn.commit()
    conn.close()


def add_loan_transaction(customer_id, tx_type, amount, note=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO loan_transactions (customer_id, timestamp, type, amount, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (customer_id, datetime.now().isoformat(), tx_type, amount, note),
    )
    conn.commit()
    conn.close()


def get_customer_loan_history(customer_id):
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT * FROM loan_transactions
        WHERE customer_id = ?
        ORDER BY timestamp DESC
        """,
        conn,
        params=(customer_id,),
    )
    conn.close()
    return df


# ========== SALES HELPERS ==========

def create_sale(store_id, customer_id, channel,
                subtotal, discount, tax, total, payment_method):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO sales (
            timestamp, store_id, customer_id, channel,
            subtotal, discount, tax, total, payment_method, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(), store_id, customer_id, channel,
            subtotal, discount, tax, total, payment_method, "Completed"
        ),
    )
    sale_id = c.lastrowid
    conn.commit()
    conn.close()
    return sale_id


def add_sale_item(sale_id, product_id, qty, unit_price, line_total):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO sale_items (sale_id, product_id, qty, unit_price, line_total)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sale_id, product_id, qty, unit_price, line_total),
    )
    conn.commit()
    conn.close()


def get_today_detailed_sales(selected_date: date, store_id=None):
    conn = get_connection()
    sdf = selected_date.isoformat()
    query = """
        SELECT s.id AS sale_id,
               s.timestamp,
               s.channel,
               c.name AS customer_name,
               p.name AS product_name,
               si.qty,
               si.unit_price,
               si.line_total,
               s.payment_method
        FROM sales s
        JOIN sale_items si ON s.id = si.sale_id
        JOIN products p ON si.product_id = p.id
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE date(s.timestamp) = ?
    """
    params = [sdf]
    if store_id is not None:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += " ORDER BY s.timestamp DESC"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_sales_by_date(selected_date: date, store_id=None):
    conn = get_connection()
    sdf = selected_date.isoformat()
    query = """
        SELECT s.id AS sale_id, s.timestamp,
               c.name AS customer_name,
               s.channel,
               s.subtotal, s.discount, s.tax, s.total,
               s.payment_method
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE date(s.timestamp) = ?
    """
    params = [sdf]
    if store_id is not None:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += " ORDER BY s.timestamp DESC"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_top_selling_products(days=7, limit=10, store_id=None):
    conn = get_connection()
    start = (date.today() - timedelta(days=days)).isoformat()
    query = """
        SELECT p.name,
               SUM(si.qty) AS total_qty,
               SUM(si.line_total) AS total_sales
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        JOIN products p ON si.product_id = p.id
        WHERE date(s.timestamp) >= ?
    """
    params = [start]
    if store_id is not None:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += """
        GROUP BY p.name
        ORDER BY total_qty DESC
        LIMIT ?
    """
    params.append(limit)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_reorder_candidates(days=7, min_qty_sold=5, store_id=None):
    conn = get_connection()
    start = (date.today() - timedelta(days=days)).isoformat()
    query = """
        SELECT p.id, p.name,
               sl.quantity AS stock,
               p.reorder_level,
               IFNULL(SUM(si.qty), 0) AS sold_qty
        FROM products p
        JOIN stock_levels sl
            ON p.id = sl.product_id
        LEFT JOIN sale_items si ON p.id = si.product_id
        LEFT JOIN sales s ON si.sale_id = s.id
             AND date(s.timestamp) >= ?
        WHERE sl.store_id = ?
        GROUP BY p.id, p.name, sl.quantity, p.reorder_level
        HAVING sold_qty >= ? AND sl.quantity <= p.reorder_level
        ORDER BY sold_qty DESC
    """
    params = [start, store_id, min_qty_sold]

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# ========== ML HELPERS: DEMAND PREDICTION ==========

def get_daily_product_sales(product_id, store_id=None, days=60):
    """
    Return a DataFrame with columns: 'day' (datetime.date) and 'qty'
    for the last `days` days of sales for one product.
    """
    conn = get_connection()
    start = (date.today() - timedelta(days=days)).isoformat()
    query = """
        SELECT date(s.timestamp) AS day,
               SUM(si.qty) AS qty
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE si.product_id = ?
          AND date(s.timestamp) >= ?
    """
    params = [product_id, start]
    if store_id is not None:
        query += " AND s.store_id = ?"
        params.append(store_id)
    query += " GROUP BY date(s.timestamp) ORDER BY day"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return df

    df["day"] = pd.to_datetime(df["day"]).dt.date
    return df


@st.cache_data
def train_demand_model(daily_df):
    """
    Train a simple LinearRegression model on daily quantity.
    X: day index (0,1,2,...)
    y: qty
    """
    if daily_df.empty or len(daily_df) < 3:
        return None

    daily_df = daily_df.sort_values("day")
    X = np.arange(len(daily_df)).reshape(-1, 1)
    y = daily_df["qty"].values

    model = LinearRegression()
    model.fit(X, y)
    return model


def predict_future_demand(daily_df, model, horizon_days=7):
    """
    Given history and a trained model, predict demand for the next horizon_days.
    Returns a DataFrame with 'day' and 'predicted_qty'.
    """
    if model is None or daily_df.empty:
        return pd.DataFrame(columns=["day", "predicted_qty"])

    last_index = len(daily_df) - 1
    future_indices = np.arange(last_index + 1, last_index + 1 + horizon_days).reshape(-1, 1)
    preds = model.predict(future_indices)
    preds = np.maximum(preds, 0)

    last_day = max(daily_df["day"])
    future_days = [last_day + timedelta(days=i + 1) for i in range(horizon_days)]

    return pd.DataFrame({
        "day": future_days,
        "predicted_qty": preds
    })


# ========== ML HELPERS: ANOMALY DETECTION ==========

def get_daily_store_sales(store_id=None, days=90):
    """
    Return a DataFrame with 'day' and 'total_sales' for the last `days` days.
    """
    conn = get_connection()
    start = (date.today() - timedelta(days=days)).isoformat()
    query = """
        SELECT date(timestamp) AS day,
               SUM(total) AS total_sales
        FROM sales
        WHERE date(timestamp) >= ?
    """
    params = [start]
    if store_id is not None:
        query += " AND store_id = ?"
        params.append(store_id)
    query += " GROUP BY date(timestamp) ORDER BY day"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        return df

    df["day"] = pd.to_datetime(df["day"]).dt.date
    return df


@st.cache_data
def detect_sales_anomalies(daily_df, contamination=0.05):
    """
    Use IsolationForest to flag anomalous days.
    Returns a copy of daily_df with an extra 'anomaly' column (True/False).
    """
    if daily_df.empty or len(daily_df) < 10:
        return daily_df.assign(anomaly=False)

    X = daily_df["total_sales"].values.reshape(-1, 1)

    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=42
    )
    model.fit(X)
    preds = model.predict(X)  # -1 = anomaly, 1 = normal

    daily_df = daily_df.copy()
    daily_df["anomaly"] = preds == -1
    return daily_df


# ========== RECEIPT HELPER ==========

def format_receipt(
    sale_id,
    customer_name,
    store_name,
    channel,
    cart_items,
    subtotal,
    discount,
    tax,
    total,
    payment_method,
    supermarket_name,
    slogan,
    cashier_name,
):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = []
    lines.append("***** SUPERMARKET RECEIPT *****")
    lines.append(f"{supermarket_name}")
    if slogan:
        lines.append(slogan)
    lines.append("")
    lines.append(f"Store: {store_name}")
    lines.append(f"Sale ID: {sale_id}")
    lines.append(f"Date/Time: {now_str}")
    if cashier_name:
        lines.append(f"Cashier: {cashier_name}")
    if customer_name:
        lines.append(f"Customer: {customer_name}")
    lines.append(f"Channel: {channel}")
    lines.append(f"Payment: {payment_method}")
    lines.append("------------------------------")
    for item in cart_items:
        name = item["name"]
        qty = item["qty"]
        price = item["price"]
        line_total = qty * price
        lines.append(f"{name} x{qty} @ {price:.2f} = {line_total:.2f}")
    lines.append("------------------------------")
    lines.append(f"Subtotal: {subtotal:.2f}")
    lines.append(f"Discount: {discount:.2f}")
    lines.append(f"Tax:     {tax:.2f}")
    lines.append(f"TOTAL:   {total:.2f}")
    lines.append("")
    lines.append("Thank you for shopping with us!")
    return "\n".join(lines)


# ========== STREAMLIT APP ==========

init_db()
st.set_page_config(page_title="Supermarket App", layout="wide")

# ── Permanent background image ──────────────────────────────────────────────
def _inject_background():
    import base64
    bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")
    if not os.path.exists(bg_path):
        return
    with open(bg_path, "rb") as _f:
        _b64 = base64.b64encode(_f.read()).decode()
    st.markdown(f"""
    <style>
    /* ── Full-page background image ── */
    .stApp {{
        background-image: url("data:image/png;base64,{_b64}");
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
        background-position: center center;
    }}

    /* ── Transparent inner wrappers so image shows through ── */
    .stMain, .stMainBlockContainer,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewBlockContainer"] {{
        background: transparent !important;
    }}

    /* ── Lighter overlay — image stays visible ── */
    .stApp::before {{
        content: "";
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.32);
        z-index: 0;
        pointer-events: none;
    }}

    /* ── Main content: thin frosted-glass card ── */
    .main .block-container {{
        background: rgba(5, 12, 22, 0.55) !important;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.12);
        padding: 2rem 2.5rem;
        margin-top: 0.8rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.40);
    }}

    /* ── Sidebar: dark glass ── */
    section[data-testid="stSidebar"] {{
        background: rgba(5, 15, 30, 0.80) !important;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border-right: 1px solid rgba(255,255,255,0.10);
    }}
    section[data-testid="stSidebar"] > div {{
        background: transparent !important;
    }}

    /* ── All text white ── */
    h1, h2, h3, h4, h5, h6 {{
        color: #ffffff !important;
        text-shadow: 0 2px 8px rgba(0,0,0,0.8);
        font-weight: 700;
    }}
    .stMarkdown p, label,
    .stTextInput label, .stNumberInput label,
    .stSelectbox label, .stRadio label,
    .stCheckbox label, p, span {{
        color: #e8f0fe !important;
        text-shadow: 0 1px 4px rgba(0,0,0,0.6);
    }}

    /* ── Sidebar text ── */
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {{
        color: #d0e8ff !important;
    }}

    /* ── Buttons: green gradient ── */
    .stButton > button {{
        background: linear-gradient(135deg, #145a32 0%, #27ae60 100%) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px;
        font-weight: 700;
        font-size: 0.95rem;
        letter-spacing: 0.4px;
        padding: 0.5rem 1.4rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        box-shadow: 0 4px 14px rgba(39,174,96,0.35);
    }}
    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(39,174,96,0.55) !important;
    }}

    /* ── Input fields ── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea textarea {{
        background: rgba(255,255,255,0.10) !important;
        color: #f0f4ff !important;
        border: 1px solid rgba(255,255,255,0.25) !important;
        border-radius: 8px;
    }}

    /* ── Selectbox ── */
    .stSelectbox > div > div,
    [data-testid="stSelectbox"] > div {{
        background: rgba(255,255,255,0.10) !important;
        color: #f0f4ff !important;
        border: 1px solid rgba(255,255,255,0.25) !important;
        border-radius: 8px;
    }}

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {{
        background: rgba(0,0,0,0.30) !important;
        border-radius: 10px;
    }}

    /* ── Metrics ── */
    [data-testid="metric-container"] {{
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 12px;
        padding: 0.6rem 1rem;
    }}

    /* ── Alerts ── */
    [data-testid="stAlert"] {{
        background: rgba(0,0,0,0.40) !important;
        border-radius: 10px;
    }}

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {{ width: 5px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{
        background: rgba(39,174,96,0.5);
        border-radius: 3px;
    }}
    </style>
    """, unsafe_allow_html=True)

_inject_background()
# ────────────────────────────────────────────────────────────────────────────

# Session
if "cart" not in st.session_state:
    st.session_state.cart = []

# Branding & invoice settings in session
if "branding" not in st.session_state:
    st.session_state.branding = {
        "name": "My Supermarket",
        "slogan": "Best prices in town",
        "cashier": "",
        "logo_bytes": None,
        "bg_css": "",
    }

# Choose store
stores_df = get_stores()
if stores_df.empty:
    st.sidebar.error("No stores found. The database may not have initialized correctly.")
    st.stop()
store_options = [f"{row['id']} - {row['name']}" for _, row in stores_df.iterrows()]
selected_store = st.sidebar.selectbox("Current store", store_options)
current_store_id = int(selected_store.split(" - ")[0])
current_store_name = selected_store.split(" - ")[1].strip()

# ---- Branding / Appearance controls ----
st.sidebar.markdown("### Branding / Appearance")

# Supermarket name & slogan
st.session_state.branding["name"] = st.sidebar.text_input(
    "Supermarket name",
    value=st.session_state.branding["name"]
)
st.session_state.branding["slogan"] = st.sidebar.text_input(
    "Slogan",
    value=st.session_state.branding["slogan"]
)

# Cashier name (used on receipts / invoices)
st.session_state.branding["cashier"] = st.sidebar.text_input(
    "Current cashier name",
    value=st.session_state.branding["cashier"],
    help="This name will appear on the invoice/receipt."
)

# Logo upload
logo_file = st.sidebar.file_uploader(
    "Logo image (PNG/JPG)",
    type=["png", "jpg", "jpeg"],
    help="Used on the on-screen invoice section."
)
if logo_file is not None:
    st.session_state.branding["logo_bytes"] = logo_file.read()

# Background image upload (for app UI)
bg_file = st.sidebar.file_uploader(
    "Background image (for app UI)",
    type=["png", "jpg", "jpeg"],
    key="bg_upload",
    help="Optional: sets a background image for the app."
)
if bg_file is not None:
    import base64
    bg_bytes = bg_file.read()
    encoded = base64.b64encode(bg_bytes).decode()
    st.session_state.branding["bg_css"] = f"""
    <style>
    .stApp {{
        background-image: url("data:image/png;base64,{encoded}");
        background-size: cover;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    </style>
    """

# Apply background CSS if set
if st.session_state.branding["bg_css"]:
    st.markdown(st.session_state.branding["bg_css"], unsafe_allow_html=True)

page = st.sidebar.radio(
    "Menu",
    ["POS", "Inventory", "Analytics", "Daily Reports", "Customers & Loans"],
)

# Global low-stock alert for this store
low_stock_df = get_low_stock_products_for_store(current_store_id)
if not low_stock_df.empty:
    st.sidebar.warning(
        f"Low stock on {len(low_stock_df)} item(s) in this store."
    )

# ================= POS PAGE =================
if page == "POS":
    st.title("Point of Sale (POS)")

    customers_df = get_all_customers()
    customer_names = ["Guest (no credit)"] + [
        f"{row['id']} - {row['name']}" for _, row in customers_df.iterrows()
    ]
    selected_customer = st.selectbox("Customer", customer_names)

    customer_id = None
    customer_record = None
    if selected_customer != "Guest (no credit)":
        cid = int(selected_customer.split(" - ")[0])
        customer_id = cid
        customer_record = get_customer_by_id(cid)
        st.write(
            f"Credit limit: {customer_record['credit_limit']:.2f}, "
            f"Current balance: {customer_record['balance']:.2f}"
        )

    channel = st.selectbox("Sales channel", ["In-store", "Online"])

    st.markdown("---")
    st.subheader("Scan or add products")

    col_barcode, col_qty = st.columns([3, 1])
    with col_barcode:
        barcode_input = st.text_input(
            "Barcode",
            help="Click here and scan with barcode scanner, or type manually."
        )
    with col_qty:
        qty_input = st.number_input("Qty", min_value=1, value=1, step=1)

    add_cols = st.columns(3)
    with add_cols[0]:
        add_barcode_btn = st.button("Add by barcode")
    with add_cols[1]:
        products_df = get_all_products()
        product_names = ["-- select product --"] + products_df["name"].tolist()
        selected_name = st.selectbox("Or choose product", product_names)
    with add_cols[2]:
        add_selected_btn = st.button("Add selected product")

    def add_to_cart(product_row, qty):
        if product_row is None:
            st.error("Product not found.")
            return
        pid = int(product_row["id"])
        available = get_stock(current_store_id, pid)
        if available <= 0:
            st.error(f"No stock for {product_row['name']} in this store.")
            return
        if qty > available:
            st.error(f"Not enough stock. Available: {available}")
            return

        for item in st.session_state.cart:
            if item["id"] == pid:
                if item["qty"] + qty > available:
                    st.error(f"Not enough stock after adding. Available: {available}")
                    return
                item["qty"] += qty
                break
        else:
            if qty > available:
                st.error(f"Not enough stock. Available: {available}")
                return
            st.session_state.cart.append({
                "id": pid,
                "name": product_row["name"],
                "price": float(product_row["price"]),
                "qty": int(qty),
            })

    if add_barcode_btn and barcode_input:
        prod = get_product_by_barcode(barcode_input)
        add_to_cart(prod, qty_input)

    if add_selected_btn and selected_name != "-- select product --":
        prod_row = products_df[products_df["name"] == selected_name]
        if not prod_row.empty:
            add_to_cart(prod_row.iloc[0], qty_input)
        else:
            st.error("Selected product not found in DB.")

    if st.session_state.cart:
        st.subheader("Cart")

        cart_items = st.session_state.cart
        total_rows = []
        remove_flags = []

        for idx, item in enumerate(cart_items):
            c1, c2, c3, c4, c5 = st.columns([4, 2, 2, 2, 1])
            with c1:
                st.write(item["name"])
            with c2:
                max_stock = get_stock(current_store_id, item["id"])
                new_qty = st.number_input(
                    f"Qty_{idx}",
                    min_value=1,
                    max_value=max_stock if max_stock > 0 else None,
                    value=item["qty"],
                    step=1,
                    key=f"qty_{idx}",
                )
                item["qty"] = new_qty
            with c3:
                st.write(f"{item['price']:.2f}")
            line_total = item["qty"] * item["price"]
            with c4:
                st.write(f"{line_total:.2f}")
            with c5:
                remove = st.checkbox("Remove", key=f"rem_{idx}")
                remove_flags.append(remove)
            total_rows.append(line_total)

        if any(remove_flags):
            st.session_state.cart = [
                item for item, rem in zip(cart_items, remove_flags) if not rem
            ]
            st.success("Item(s) removed from cart.")
            st.rerun()

        subtotal = sum(total_rows)

        st.markdown("---")
        st.subheader("Totals, Discount & Tax")

        col_sub, col_disc, col_tax = st.columns(3)
        with col_sub:
            st.write(f"Subtotal: **{subtotal:.2f}**")
        with col_disc:
            discount_type = st.selectbox("Discount type", ["None", "%", "Fixed"])
            if discount_type == "%":
                disc_pct = st.number_input("Discount (%)", min_value=0.0, value=0.0, step=0.5)
                discount = subtotal * disc_pct / 100
            elif discount_type == "Fixed":
                discount = st.number_input("Discount amount", min_value=0.0, value=0.0, step=0.5)
            else:
                discount = 0.0
        with col_tax:
            tax_rate = st.number_input("Tax rate (%)", min_value=0.0, value=0.0, step=0.5)
            tax = (subtotal - discount) * tax_rate / 100 if subtotal > discount else 0.0

        total = subtotal - discount + tax
        st.write(f"**Total to pay: {total:.2f}**")

        payment_method = st.selectbox(
            "Payment method",
            ["Cash", "Card", "Mobile Money", "Store Credit"]
        )

        if st.button("Complete sale & print receipt"):
            if not st.session_state.cart:
                st.error("Cart is empty.")
            else:
                if payment_method == "Store Credit":
                    if customer_id is None:
                        st.error("Select a registered customer to use Store Credit.")
                        st.stop()
                    cust = customer_record
                    new_balance = float(cust["balance"]) + float(total)
                    if new_balance > float(cust["credit_limit"]):
                        st.error(
                            f"Credit limit exceeded! "
                            f"Limit: {cust['credit_limit']:.2f}, "
                            f"current: {cust['balance']:.2f}, "
                            f"trying to add: {total:.2f}"
                        )
                        st.stop()

                sale_id = create_sale(
                    store_id=current_store_id,
                    customer_id=customer_id,
                    channel=channel,
                    subtotal=subtotal,
                    discount=discount,
                    tax=tax,
                    total=total,
                    payment_method=payment_method,
                )

                for item in st.session_state.cart:
                    pid = item["id"]
                    qty = item["qty"]
                    price = item["price"]
                    line_total = qty * price
                    add_sale_item(sale_id, pid, qty, price, line_total)
                    update_stock_after_sale(current_store_id, pid, qty)

                if payment_method == "Store Credit":
                    update_customer_balance(customer_id, new_balance)
                    add_loan_transaction(
                        customer_id,
                        tx_type="credit_purchase",
                        amount=total,
                        note=f"Sale #{sale_id}",
                    )

                customer_name = customer_record["name"] if customer_record is not None else ""

                branding = st.session_state.branding
                receipt_text = format_receipt(
                    sale_id,
                    customer_name,
                    current_store_name,
                    channel,
                    st.session_state.cart,
                    subtotal,
                    discount,
                    tax,
                    total,
                    payment_method,
                    supermarket_name=branding["name"],
                    slogan=branding["slogan"],
                    cashier_name=branding["cashier"],
                )

                st.success(f"Sale #{sale_id} completed.")
                st.text_area("Receipt", receipt_text, height=250)

                buf = io.BytesIO(receipt_text.encode("utf-8"))
                st.download_button(
                    label="Download receipt (.txt)",
                    data=buf,
                    file_name=f"receipt_{sale_id}.txt",
                    mime="text/plain",
                )

                # HTML invoice with logo for browser print
                st.markdown("---")
                st.subheader("Invoice preview (with logo)")

                html_parts = []
                if branding["logo_bytes"] is not None:
                    import base64
                    logo_b64 = base64.b64encode(branding["logo_bytes"]).decode()
                    html_parts.append(
                        f'<img src="data:image/png;base64,{logo_b64}" '
                        f'style="height:80px; margin-bottom:8px;" />'
                    )
                html_parts.append(f"<h2 style='margin:0;'>{branding['name']}</h2>")
                if branding["slogan"]:
                    html_parts.append(f"<p style='margin:0; color:grey;'>{branding['slogan']}</p>")
                html_parts.append("<hr>")
                html_parts.append(
                    f"<p><b>Store:</b> {current_store_name} "
                    f"&nbsp;&nbsp; <b>Sale ID:</b> {sale_id} "
                    f"&nbsp;&nbsp; <b>Date/Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
                )
                if branding["cashier"]:
                    html_parts.append(f"<p><b>Cashier:</b> {branding['cashier']}</p>")
                if customer_name:
                    html_parts.append(f"<p><b>Customer:</b> {customer_name}</p>")
                html_parts.append(
                    f"<p><b>Channel:</b> {channel} &nbsp;&nbsp; "
                    f"<b>Payment:</b> {payment_method}</p>"
                )
                html_parts.append("<hr>")

                html_parts.append("<table style='width:100%; border-collapse:collapse;'>")
                html_parts.append(
                    "<tr>"
                    "<th style='border-bottom:1px solid #ccc; text-align:left;'>Item</th>"
                    "<th style='border-bottom:1px solid #ccc; text-align:right;'>Qty</th>"
                    "<th style='border-bottom:1px solid #ccc; text-align:right;'>Price</th>"
                    "<th style='border-bottom:1px solid #ccc; text-align:right;'>Total</th>"
                    "</tr>"
                )
                for it in st.session_state.cart:
                    lt = it['qty'] * it['price']
                    html_parts.append(
                        "<tr>"
                        f"<td>{it['name']}</td>"
                        f"<td style='text-align:right;'>{it['qty']}</td>"
                        f"<td style='text-align:right;'>{it['price']:.2f}</td>"
                        f"<td style='text-align:right;'>{lt:.2f}</td>"
                        "</tr>"
                    )
                html_parts.append("</table>")

                html_parts.append("<hr>")
                html_parts.append(
                    f"<p>Subtotal: {subtotal:.2f}<br>"
                    f"Discount: {discount:.2f}<br>"
                    f"Tax: {tax:.2f}<br>"
                    f"<b>TOTAL: {total:.2f}</b></p>"
                )

                st.markdown(
                    "<div style='background:white; padding:10px;'>"
                    + "".join(html_parts) +
                    "</div>",
                    unsafe_allow_html=True,
                )

                st.info(
                    "To print this invoice with logo, use your browser: "
                    "Ctrl+P (Print) → select printer or 'Save as PDF'."
                )

                # Clear cart after everything
                st.session_state.cart = []

    else:
        st.info("Cart is empty. Add items by barcode or selection.")

# ================= INVENTORY PAGE =================
elif page == "Inventory":
    st.title("Inventory Management")

    st.subheader(f"Inventory for {current_store_name}")
    inv_df = get_inventory_for_store(current_store_id)
    if inv_df.empty:
        st.info("No products yet.")
    else:
        st.dataframe(inv_df)

    st.markdown("---")
    st.subheader("Low-stock items")
    if low_stock_df.empty:
        st.success("No low-stock items in this store.")
    else:
        st.warning("These items are low in stock:")
        st.dataframe(low_stock_df)

    st.markdown("---")
    st.subheader("Add / update product")

    with st.form("add_product"):
        name = st.text_input("Name")
        barcode = st.text_input("Barcode")
        price = st.number_input("Price", min_value=0.0, step=0.1)
        reorder_level = st.number_input("Reorder level", min_value=0, value=5, step=1)
        initial_stock = st.number_input("Initial stock (for current store)", min_value=0, step=1)
        submitted = st.form_submit_button("Save")
        if submitted:
            if not name or not barcode:
                st.error("Name and barcode are required.")
            else:
                try:
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute(
                        """
                        INSERT INTO products (name, barcode, price, reorder_level, is_active)
                        VALUES (?, ?, ?, ?, 1)
                        ON CONFLICT(barcode)
                        DO UPDATE SET
                            name=excluded.name,
                            price=excluded.price,
                            reorder_level=excluded.reorder_level,
                            is_active=1
                        """,
                        (name, barcode, price, reorder_level),
                    )
                    c.execute("SELECT id FROM products WHERE barcode = ?", (barcode,))
                    pid = c.fetchone()[0]
                    conn.commit()
                    conn.close()

                    set_stock(current_store_id, pid, initial_stock)

                    st.success("Product saved/updated and stock set for this store.")
                except Exception as e:
                    st.error(f"Error: {e}")

# ================= ANALYTICS PAGE =================
elif page == "Analytics":
    st.title("Sales & Inventory Analytics")

    col_days, col_min = st.columns(2)
    with col_days:
        days = st.number_input("Look back (days)", min_value=1, value=7, step=1)
    with col_min:
        min_sold = st.number_input("Min qty sold for reorder alert", min_value=1, value=5, step=1)

    st.subheader("Fast-moving items (highest sales)")
    top_df = get_top_selling_products(days=days, limit=10, store_id=current_store_id)
    if top_df.empty:
        st.info("No sales in selected period.")
    else:
        st.dataframe(top_df)
        st.bar_chart(top_df.set_index("name")["total_qty"])

    st.markdown("---")
    st.subheader("Reorder suggestions (high sales + low stock)")
    reorder_df = get_reorder_candidates(days=days, min_qty_sold=min_sold, store_id=current_store_id)
    if reorder_df.empty:
        st.success("No immediate reorder needs based on current criteria.")
    else:
        st.warning("Consider reordering these items:")
        st.dataframe(reorder_df)

    # ---- Demand prediction (per product) ----
    st.markdown("---")
    st.subheader("Demand prediction (per product)")

    all_products = get_all_products()
    if all_products.empty:
        st.info("No products to predict.")
    else:
        prod_options = [
            f"{row['id']} - {row['name']}"
            for _, row in all_products.iterrows()
        ]
        selected_prod = st.selectbox("Select product", prod_options)
        prod_id = int(selected_prod.split(" - ")[0])
        prod_row = get_product_by_id(prod_id)

        horizon = st.number_input("Forecast horizon (days)", min_value=1, value=7, step=1)

        daily_sales = get_daily_product_sales(prod_id, store_id=current_store_id, days=60)
        if daily_sales.empty or len(daily_sales) < 3:
            st.warning("Not enough sales history for this product to train a model.")
        else:
            model = train_demand_model(daily_sales)
            future = predict_future_demand(daily_sales, model, horizon_days=horizon)

            st.write("Recent daily sales (last 60 days or less):")
            st.dataframe(daily_sales)

            st.write("Predicted future daily demand:")
            st.dataframe(future)

            total_future = future["predicted_qty"].sum()
            current_stock = get_stock(current_store_id, prod_id)
            st.write(f"Current stock: **{current_stock}** units")
            st.write(f"Predicted demand next {horizon} days: **{total_future:.1f}** units")

            if total_future > current_stock:
                needed = total_future - current_stock
                st.warning(
                    f"Stock may be insufficient. "
                    f"Suggested reorder (approx.): {needed:.1f} units."
                )
            else:
                st.success("Current stock seems sufficient for the forecast horizon.")

    # ---- Anomaly detection on daily sales ----
    st.markdown("---")
    st.subheader("Anomaly detection on daily sales")

    contamination = st.slider(
        "Anomaly sensitivity (higher = more days flagged)",
        min_value=0.01,
        max_value=0.20,
        value=0.05,
        step=0.01,
    )

    daily_store_sales = get_daily_store_sales(store_id=current_store_id, days=90)
    if daily_store_sales.empty:
        st.info("No sales data yet for anomaly detection.")
    else:
        detected = detect_sales_anomalies(daily_store_sales, contamination=contamination)
        st.write("Daily total sales (last 90 days):")
        st.dataframe(detected)

        anomalies = detected[detected["anomaly"]]
        if anomalies.empty:
            st.success("No anomalous days detected with current settings.")
        else:
            st.warning("Anomalous days detected:")
            st.dataframe(anomalies)

        chart_df = detected.copy()
        chart_df["day"] = pd.to_datetime(chart_df["day"])
        chart_df = chart_df.set_index("day")
        st.line_chart(chart_df["total_sales"])

# ================= DAILY REPORTS PAGE =================
elif page == "Daily Reports":
    st.title("Daily Sales Reports")

    report_date = st.date_input("Select date", value=date.today())
    detailed_df = get_today_detailed_sales(report_date, store_id=current_store_id)

    if detailed_df.empty:
        st.info("No sales for selected date/store.")
    else:
        st.subheader("Detailed line items")
        st.dataframe(detailed_df)

        st.subheader("Summary by sale (receipt)")
        header_df = get_sales_by_date(report_date, store_id=current_store_id)
        st.dataframe(header_df)

        total_sales = header_df["total"].sum() if not header_df.empty else 0.0
        st.write(f"**Total sales for {report_date} ({current_store_name}): {total_sales:.2f}**")

        csv_buffer = io.StringIO()
        detailed_df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download detailed report as CSV",
            data=csv_buffer.getvalue(),
            file_name=f"sales_{current_store_name}_{report_date}.csv",
            mime="text/csv",
        )

        st.info("For PDF, use your browser: Print → Save as PDF.")

# ================= CUSTOMERS & LOANS PAGE =================
else:  # Customers & Loans
    st.title("Customers & Loans (Store Credit)")

    st.subheader("Add new customer")
    with st.form("add_customer"):
        cname = st.text_input("Name")
        cphone = st.text_input("Phone")
        climit = st.number_input("Credit limit", min_value=0.0, value=0.0, step=10.0)
        submitted = st.form_submit_button("Save customer")
        if submitted:
            if not cname:
                st.error("Name is required.")
            else:
                create_customer(cname, cphone, climit)
                st.success("Customer created.")

    st.markdown("---")
    st.subheader("Customer list")

    customers_df = get_all_customers()
    if customers_df.empty:
        st.info("No customers yet.")
    else:
        st.dataframe(customers_df)

        options = [
            f"{row['id']} - {row['name']}"
            for _, row in customers_df.iterrows()
        ]
        selected = st.selectbox("View customer", options)
        cid = int(selected.split(" - ")[0])
        cust = get_customer_by_id(cid)

        st.write(
            f"**{cust['name']}** – Phone: {cust['phone']}, "
            f"Credit limit: {cust['credit_limit']:.2f}, "
            f"Current balance: {cust['balance']:.2f}"
        )

        st.subheader("Record repayment")
        repay_amount = st.number_input(
            "Repayment amount",
            min_value=0.0,
            step=10.0,
            value=0.0,
        )
        repay_note = st.text_input("Note (optional)", value="Cash repayment")
        if st.button("Save repayment"):
            if repay_amount <= 0:
                st.error("Repayment amount must be > 0.")
            elif repay_amount > float(cust["balance"]):
                st.error("Repayment cannot be more than current balance.")
            else:
                new_balance = float(cust["balance"]) - repay_amount
                update_customer_balance(cid, new_balance)
                add_loan_transaction(
                    cid,
                    tx_type="repayment",
                    amount=repay_amount,
                    note=repay_note,
                )
                st.success("Repayment recorded.")
                st.rerun()

        st.subheader("Loan / credit history")
        history_df = get_customer_loan_history(cid)
        if history_df.empty:
            st.info("No loan transactions for this customer.")
        else:
            st.dataframe(history_df)
