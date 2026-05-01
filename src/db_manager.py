"""SQLite: история расчётов + диалоговое состояние пользователей."""
import sqlite3
import threading

from src.config import DB_PATH

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with _lock:
        cur = _conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS calculations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            rate REAL NOT NULL,
            months INTEGER NOT NULL,
            overpayment REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS state(
            user_id INTEGER PRIMARY KEY,
            mode    TEXT,
            step    TEXT,
            amount  REAL,
            rate    REAL,
            months  INTEGER
        )""")
        _conn.commit()


# ── история ─────────────────────────────────────────────────────────────
def save_calc(user_id: int, c_type: str, amount: float,
              rate: float, months: int, overpayment: float):
    with _lock:
        _conn.execute(
            "INSERT INTO calculations(user_id, type, amount, rate, months, "
            "overpayment) VALUES(?,?,?,?,?,?)",
            (user_id, c_type, amount, rate, months, overpayment),
        )
        _conn.commit()


def get_history(user_id: int, limit: int = 5):
    with _lock:
        rows = _conn.execute(
            "SELECT type, amount, rate, months, overpayment, created_at "
            "FROM calculations WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return rows


# ── состояние диалога ───────────────────────────────────────────────────
def get_state(user_id: int):
    with _lock:
        row = _conn.execute(
            "SELECT mode, step, amount, rate, months FROM state "
            "WHERE user_id=?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return dict(zip(["mode", "step", "amount", "rate", "months"], row))


def set_state(user_id: int, **kw):
    cur = get_state(user_id) or {
        "mode": None, "step": None,
        "amount": None, "rate": None, "months": None,
    }
    cur.update(kw)
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO state VALUES(?,?,?,?,?,?)",
            (user_id, cur["mode"], cur["step"],
             cur["amount"], cur["rate"], cur["months"]),
        )
        _conn.commit()


def clear_state(user_id: int):
    with _lock:
        _conn.execute("DELETE FROM state WHERE user_id=?", (user_id,))
        _conn.commit()
