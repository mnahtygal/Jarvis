import json
import psycopg2
from pathlib import Path

# ====================================
# CONFIG
# ====================================

JSON_FILE = "data/memory.json"

DB_CONFIG = {
    "host": "localhost",
    "database": "jarvis",
    "user": "mnahtygal",
    "password": "jarvis123"
}

# ====================================
# LOAD JSON
# ====================================

memory_path = Path(JSON_FILE)

if not memory_path.exists():
    print(f"[ERROR] File not found: {JSON_FILE}")
    exit()

with open(memory_path, "r") as f:
    data = json.load(f)

facts = data.get("facts", {})
history = data.get("history", [])

print(f"[INFO] Loaded {len(facts)} facts")
print(f"[INFO] Loaded {len(history)} history events")

# ====================================
# CONNECT TO POSTGRES
# ====================================

conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

# ====================================
# MIGRATE FACTS
# ====================================

fact_count = 0

for key, value in facts.items():

    cursor.execute("""
        INSERT INTO memories (
            memory_key,
            memory_value
        )
        VALUES (%s, %s)

        ON CONFLICT (memory_key)
        DO UPDATE SET
            memory_value = EXCLUDED.memory_value,
            updated_at = CURRENT_TIMESTAMP;
    """, (key, str(value)))

    fact_count += 1

    print(f"[FACT] {key} = {value}")

# ====================================
# MIGRATE HISTORY
# ====================================

history_count = 0

for event in history:

    action_type = event.get("type")
    memory_key = event.get("key")

    old_value = event.get("old_value")
    new_value = (
        event.get("new_value")
        or event.get("value")
    )

    timestamp = event.get("timestamp")

    cursor.execute("""
        INSERT INTO memory_history (
            action_type,
            memory_key,
            old_value,
            new_value,
            event_timestamp
        )
        VALUES (%s, %s, %s, %s, %s);
    """, (
        action_type,
        memory_key,
        old_value,
        new_value,
        timestamp
    ))

    history_count += 1

    print(f"[HISTORY] {action_type} -> {memory_key}")

# ====================================
# COMMIT
# ====================================

conn.commit()

cursor.close()
conn.close()

# ====================================
# DONE
# ====================================

print("\n==============================")
print("[SUCCESS] Migration Complete")
print(f"Facts Migrated: {fact_count}")
print(f"History Migrated: {history_count}")
print("==============================")
