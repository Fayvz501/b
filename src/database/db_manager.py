import sqlite3
from src.config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS calculations 
                   (id INTEGER PRIMARY KEY, user_id INTEGER, type TEXT, amount REAL, overpayment REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_calc(user_id, c_type, amount, overpayment):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO calculations (user_id, type, amount, overpayment) VALUES (?, ?, ?, ?)", 
                (user_id, c_type, amount, overpayment))
    conn.commit()
    conn.close()

def get_history(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT type, amount, overpayment, date FROM calculations WHERE user_id = ? ORDER BY date DESC LIMIT 5", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows