import os
import sqlite3

import pandas as pd

from wallet_utils import fingerprint

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "hamyon.db")


def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT NOT NULL,
            description TEXT,
            category TEXT,
            income REAL DEFAULT 0,
            expense REAL DEFAULT 0,
            source TEXT DEFAULT 'Manual',
            fingerprint TEXT UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,
            limit_amount REAL NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id TEXT PRIMARY KEY,
            phone_number TEXT,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            status TEXT DEFAULT 'active',
            last_active TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            admin_username TEXT,
            action TEXT NOT NULL,
            ip_address TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Status ustunini xavfsiz qo'shish (agar avvalgi jadvalda bo'lmasa)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT CURRENT_TIMESTAMP")
    except Exception:
        pass
    conn.commit()
    return conn


def get_user(conn, telegram_id):
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, phone_number, first_name, last_name, username, status, last_active, created_at FROM users WHERE telegram_id = ?", (str(telegram_id),))
    row = cur.fetchone()
    if row:
        return {
            "telegram_id": row[0],
            "phone_number": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "username": row[4],
            "status": row[5] or "active",
            "last_active": row[6] or row[7],
            "created_at": row[7],
        }
    return None


def get_all_users(conn):
    cur = conn.cursor()
    cur.execute("SELECT telegram_id, phone_number, first_name, last_name, username, status, last_active, created_at FROM users ORDER BY created_at DESC")
    users = []
    for row in cur.fetchall():
        users.append({
            "telegram_id": row[0],
            "phone_number": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "username": row[4],
            "status": row[5] or "active",
            "last_active": row[6] or row[7],
            "created_at": row[7],
        })
    return users


def update_user_status(conn, telegram_id, status):
    conn.execute("UPDATE users SET status = ? WHERE telegram_id = ?", (status, str(telegram_id)))
    conn.commit()


def update_user_activity(conn, telegram_id):
    conn.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE telegram_id = ?", (str(telegram_id),))
    conn.commit()


# Admin User Management & Audit
def hash_password(password: str) -> str:
    import hashlib
    import binascii
    salt = b"hamyon_admin_salt_sec_2026"
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return binascii.hexlify(dk).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def init_default_admin(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM admin_users")
    if cur.fetchone()[0] == 0:
        pass_hash = hash_password("admin123")
        conn.execute(
            """
            INSERT INTO admin_users (username, password_hash, full_name, role, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("admin", pass_hash, "Bosh Administrator", "superadmin", 1)
        )
        conn.commit()


def get_admin_by_username(conn, username: str):
    cur = conn.cursor()
    cur.execute("SELECT id, username, password_hash, full_name, role, is_active, last_login FROM admin_users WHERE username = ?", (username,))
    row = cur.fetchone()
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "full_name": row[3],
            "role": row[4],
            "is_active": row[5],
            "last_login": row[6]
        }
    return None


def add_audit_log(conn, admin_id, admin_username, action, ip_address="", details=""):
    conn.execute(
        """
        INSERT INTO audit_logs (admin_id, admin_username, action, ip_address, details)
        VALUES (?, ?, ?, ?, ?)
        """,
        (admin_id, admin_username, action, ip_address, details)
    )
    conn.commit()


def get_audit_logs(conn, limit=100):
    cur = conn.cursor()
    cur.execute("SELECT id, admin_id, admin_username, action, ip_address, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    logs = []
    for r in cur.fetchall():
        logs.append({
            "id": r[0],
            "admin_id": r[1],
            "admin_username": r[2],
            "action": r[3],
            "ip_address": r[4],
            "details": r[5],
            "created_at": r[6]
        })
    return logs


def register_or_update_user(conn, telegram_id, phone_number, first_name="", last_name="", username=""):
    conn.execute(
        """
        INSERT INTO users (telegram_id, phone_number, first_name, last_name, username)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            phone_number = excluded.phone_number,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            username = excluded.username
        """,
        (str(telegram_id), str(phone_number), str(first_name or ""), str(last_name or ""), str(username or "")),
    )
    conn.commit()


def add_transaction(conn, d, desc, category, income, expense, source="Manual"):
    fp = fingerprint(d, desc, income, expense)
    try:
        cur = conn.execute(
            """
            INSERT INTO transactions
            (tx_date, description, category, income, expense, source, fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (str(d), str(desc), category, float(income), float(expense), source, fp),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return False


def delete_transaction(conn, tx_id):
    conn.execute("DELETE FROM transactions WHERE id = ?", (int(tx_id),))
    conn.commit()


def update_transaction_category(conn, tx_id, category):
    conn.execute(
        "UPDATE transactions SET category = ? WHERE id = ?",
        (category, int(tx_id)),
    )
    conn.commit()


def load_data(conn):
    return pd.read_sql_query(
        "SELECT * FROM transactions ORDER BY tx_date DESC, id DESC",
        conn,
    )


def delete_all_transactions(conn):
    conn.execute("DELETE FROM transactions")
    conn.commit()


def save_budget(conn, category, limit_amount):
    conn.execute(
        """
        INSERT INTO budgets (category, limit_amount, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(category)
        DO UPDATE SET limit_amount = excluded.limit_amount, updated_at = CURRENT_TIMESTAMP
        """,
        (category, float(limit_amount)),
    )
    conn.commit()


def load_budgets(conn):
    return pd.read_sql_query("SELECT * FROM budgets ORDER BY category ASC", conn)
