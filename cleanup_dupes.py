"""One-off script to clear the entire queue for a fresh start."""
import sqlite3
from pathlib import Path

DB_PATH = Path("linkedin_bot.db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("DELETE FROM queue")
conn.commit()
print(f"Deleted {c.rowcount} rows from queue.")
conn.close()
