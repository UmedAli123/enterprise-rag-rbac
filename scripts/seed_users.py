"""Seed users from data/users.json with DEMO_PASSWORD into SQLite."""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.auth import get_db_connection, hash_password, init_db
from app.config import settings


def seed_users():
    init_db()
    users_file = Path(settings.DATA_DIR) / "users.json"
    if not users_file.exists():
        users_file = Path("./data/users.json")

    with open(users_file, "r", encoding="utf-8") as f:
        users_data = json.load(f)

    conn = get_db_connection()
    hashed_pwd = hash_password(settings.DEMO_PASSWORD)

    with conn:
        for u in users_data:
            conn.execute("""
                INSERT OR REPLACE INTO users (username, name, role, department, password_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (u["username"], u["name"], u["role"], u["department"], hashed_pwd))

    conn.close()
    print(f"Successfully seeded {len(users_data)} users with demo password.")


if __name__ == "__main__":
    seed_users()
