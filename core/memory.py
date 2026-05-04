# core/memory.py

import json
import os
from datetime import datetime

MEMORY_FILE = "data/memory.json"


def _default_memory():
    return {
        "facts": {},
        "history": []
    }


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return _default_memory()

    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return _default_memory()


def save_memory(memory):
    os.makedirs("data", exist_ok=True)

    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def remember_fact(key: str, value: str):
    memory = load_memory()
    key = key.strip().lower()
    value = value.strip()

    memory["facts"][key] = value
    memory["history"].append({
        "type": "remember",
        "key": key,
        "value": value,
        "timestamp": datetime.now().isoformat()
    })

    save_memory(memory)


def update_fact(key: str, value: str):
    memory = load_memory()
    key = key.strip().lower()
    value = value.strip()

    old_value = memory["facts"].get(key)
    memory["facts"][key] = value

    memory["history"].append({
        "type": "update",
        "key": key,
        "old_value": old_value,
        "new_value": value,
        "timestamp": datetime.now().isoformat()
    })

    save_memory(memory)
    return old_value


def forget_fact(key: str):
    memory = load_memory()
    key = key.strip().lower()

    old_value = memory["facts"].pop(key, None)

    memory["history"].append({
        "type": "forget",
        "key": key,
        "old_value": old_value,
        "timestamp": datetime.now().isoformat()
    })

    save_memory(memory)
    return old_value


def recall_fact(key: str):
    memory = load_memory()
    return memory["facts"].get(key.strip().lower())


def get_all_facts():
    memory = load_memory()
    return memory.get("facts", {})
