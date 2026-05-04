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
    memory["facts"][key] = value
    memory["history"].append({
        "type": "remember",
        "key": key,
        "value": value,
        "timestamp": datetime.now().isoformat()
    })
    save_memory(memory)


def recall_fact(key: str):
    memory = load_memory()
    return memory["facts"].get(key)


def get_all_facts():
    memory = load_memory()
    return memory.get("facts", {})

