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
    conn.commit()
    return conn


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
