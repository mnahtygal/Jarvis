# core/router.py

import string

from core.camera_roles import get_camera_roles_status, set_active_camera_role
from skills.time_skill import get_time_response
from skills.system_skill import get_system_response
from skills.chat_skill import get_chat_response
from skills.llm_skill import get_llm_response
from skills.health_skill import get_health_response
from skills.help_skill import get_help_response
from skills.version_skill import get_version_response
from skills.memory_summary_skill import get_memory_summary_response
from skills.docs_skill import get_docs_response
from skills.brain_status_skill import get_brain_status_response
from skills.semantic_memory_skill import (
    get_recent_semantic_memories_response,
    get_semantic_categories_response,
    get_semantic_memories_by_category_response,
    get_semantic_memory_status_response,
    get_semantic_search_response,
)
from skills.runtime_skill import (
    get_jarvis_goal_response,
    get_memory_stack_response,
    get_model_response,
    get_platform_response,
    get_runtime_identity_response,
)

from core.memory import (
    remember,
    recall,
    update_memory,
    forget,
    get_all_memories,
)

try:
    from core.semantic_memory import add_semantic_memory, search_semantic_memories
except Exception:
    add_semantic_memory = None
    search_semantic_memories = None


def normalize_text_for_routing(command: str) -> str:
    """
    Normalize text for command routing.

    This helps voice transcripts such as:
    - "Hello, Jarvis."
    - "Brain status."
    - "What do you remember?"

    become:
    - "hello jarvis"
    - "brain status"
    - "what do you remember"

    Important:
    - The original command is still used when storing memories.
    - This normalized text is only for intent matching.
    """
    text = (command or "").lower().strip()

    translator = str.maketrans({char: " " for char in string.punctuation})
    text = text.translate(translator)

    text = " ".join(text.split())

    return text


def normalize_key(key: str) -> str:
    key = normalize_text_for_routing(key)

    if "preferred database" in key or "preference" in key or "prefer" in key:
        return "my preferred database"

    if "workplace" in key or "work" in key or "job" in key:
        return "my workplace"

    if "wife" in key:
        return "my wife's name"

    return key


def _clean_question_key(text: str) -> str:
    key = (
        text.replace("what is my ", "")
        .replace("what s my ", "")
        .replace("who is my ", "")
        .replace("who s my ", "")
        .replace("where is my ", "")
        .replace("where s my ", "")
        .replace(" called", "")
        .replace(" named", "")
        .strip()
    )

    return "my " + key

def _try_exact_memory_question(text: str):
    """
    Answer common exact-memory questions without using the LLM.

    Handles first-person and third-person phrasing:
    - what database do I prefer
    - what database does Marty prefer
    - what cruise ship does Marty like
    - what is my wife's name
    - where do I work
    """

    if "database" in text and (
        "prefer" in text
        or "preferred" in text
        or "like" in text
        or "marty" in text
    ):
        value = recall("my preferred database") or recall("my preference")
        if value:
            return f"Based on your saved memory, your preferred database is {value}, Marty."

    if "ship" in text and (
        "like" in text
        or "favorite" in text
        or "cruise" in text
        or "marty" in text
    ):
        value = recall("my favorite ship") or recall("favorite_ship")
        if value:
            return f"Based on your saved memory, your favorite ship is {value}, Marty."

    if "wife" in text:
        value = recall("my wife's name")
        if value:
            return f"Based on your saved memory, your wife's name is {value}, Marty."

    if (
        "where do i work" in text
        or "where does marty work" in text
        or "who do i work for" in text
        or "who does marty work for" in text
        or "workplace" in text
        or ("work" in text and ("where" in text or "who" in text or "marty" in text))
    ):
        value = recall("my workplace")
        if value:
            return f"Based on your saved memory, you work at {value}, Marty."

    return None

def _remember_is_fact(fact: str):
    lowered = fact.lower()

    if " is called " in lowered:
        split_text = " is called "
    elif " is named " in lowered:
        split_text = " is named "
    elif " is " in lowered:
        split_text = " is "
    else:
        return None

    index = lowered.find(split_text)

    key = fact[:index].strip()
    value = fact[index + len(split_text):].strip().strip(" .!?")

    key = normalize_key(key)

    if not key or not value:
        return None

    return remember(key, value)


def _looks_like_duplicate_semantic_note(note: str):
    """
    Check for very similar existing semantic memory.

    This is intentionally simple:
    - exact normalized content match is a duplicate
    - similarity >= 0.96 is treated as duplicate
    """
    if search_semantic_memories is None:
        return None

    cleaned = " ".join((note or "").strip().lower().split())

    if not cleaned:
        return None

    try:
        results = search_semantic_memories(note, limit=3)
    except Exception:
        return None

    for item in results:
        existing_content = " ".join(
            item.get("content", "").strip().lower().split()
        )
        similarity = float(item.get("similarity", 0.0))

        if existing_content == cleaned or similarity >= 0.96:
            return item

    return None


def _store_semantic_note(note: str) -> str:
    """
    Store freeform notes in pgvector semantic memory.
    """
    cleaned = (note or "").strip().strip(" .!?")

    if not cleaned:
        return "I can remember that, Marty, but I need something to save."

    if add_semantic_memory is None:
        return "Semantic memory is not available right now, Marty."

    duplicate = _looks_like_duplicate_semantic_note(cleaned)

    if duplicate:
        memory_id = duplicate.get("id", "?")
        similarity = float(duplicate.get("similarity", 0.0))
        return (
            f"I already have a very similar semantic memory, Marty. "
            f"Memory #{memory_id}, similarity={similarity:.3f}."
        )

    memory_id = add_semantic_memory(
        content=cleaned,
        source_type="user_note",
        source_id=None,
        metadata={
            "source": "marty",
            "capture_method": "freeform_remember",
        },
    )

    return f"I saved that to semantic memory, Marty. Memory #{memory_id}."


def _try_natural_memory(command: str):
    text = normalize_text_for_routing(command)

    if text.startswith("my ") and (
        " is called " in text
        or " is named " in text
        or " is " in text
    ):
        return _remember_is_fact(command)

    if text.startswith("i work at "):
        value = command[len("I work at "):].strip().strip(" .!?")
        return remember("my workplace", value)

    if text.startswith("i work for "):
        value = command[len("I work for "):].strip().strip(" .!?")
        return remember("my workplace", value)

    if text.startswith("i prefer "):
        value = command[len("I prefer "):].strip().strip(" .!?")
        return remember("my preferred database", value)

    if text.startswith("i like "):
        value = command[len("I like "):].strip().strip(" .!?")
        return remember("something I like", value)

    return None


def _is_runtime_identity_request(text: str) -> bool:
    runtime_phrases = [
        "what hardware are you running on",
        "what are you running on",
        "what platform are you running on",
        "what system are you running on",
        "what machine are you running on",
        "what computer are you running on",
        "what model are you using",
        "what llm are you using",
        "what ai model are you using",
        "what is your runtime",
        "what runtime are you using",
        "where are you running",
        "are you running on thor",
        "are you on thor",
        "what memory systems do you have",
        "what memory system do you have",
    ]

    if text in runtime_phrases:
        return True

    if "hardware" in text and "running" in text:
        return True

    if "platform" in text and "running" in text:
        return True

    if "model" in text and ("using" in text or "running" in text):
        return True

    if "llm" in text and ("using" in text or "running" in text):
        return True

    if "runtime" in text and ("using" in text or "running" in text):
        return True

    if "memory systems" in text or "memory system" in text:
        return True

    return False


def _is_jarvis_goal_request(text: str) -> bool:
    goal_phrases = [
        "what is the long term goal for jarvis",
        "what is the long term goal of jarvis",
        "what is jarvis long term goal",
        "what is jarvis goal",
        "what are jarvis goals",
        "where is jarvis going",
        "what are we building jarvis into",
        "what are we building jarvis for",
        "what is the goal for jarvis",
        "what is the goal of jarvis",
    ]

    if text in goal_phrases:
        return True

    if "jarvis" in text and "goal" in text:
        return True

    if "jarvis" in text and "long term" in text:
        return True

    if "jarvis" in text and "building" in text:
        return True

    return False


def _is_health_check_request(text: str) -> bool:
    health_phrases = [
        "jarvis health",
        "health check",
        "system health",
        "jarvis status",
        "status check",
        "are you healthy",
        "are you ok",
        "are you okay",
    ]

    return any(phrase in text for phrase in health_phrases)


def _is_help_request(text: str) -> bool:
    help_phrases = [
        "jarvis help",
        "help",
        "what can you do",
        "what can jarvis do",
        "show commands",
        "list commands",
        "capabilities",
        "jarvis capabilities",
    ]

    return text in help_phrases


def _is_version_request(text: str) -> bool:
    version_phrases = [
        "jarvis version",
        "version",
        "build info",
        "jarvis build",
        "jarvis build info",
        "what version are you",
        "what version is jarvis",
    ]

    return text in version_phrases


def _is_memory_summary_request(text: str) -> bool:
    memory_summary_phrases = [
        "jarvis memory summary",
        "memory summary",
        "summarize memory",
        "summarize memories",
        "memory status",
        "what is in memory",
        "show memory",
        "show memories",
    ]

    return text in memory_summary_phrases


def _try_camera_role_command(text: str):
    workbench_phrases = [
        "switch to workbench camera",
        "use logitech camera",
        "use the logitech camera",
        "look at the workbench",
        "look at workbench",
    ]
    face_phrases = [
        "switch to face camera",
        "use insta360",
        "use the insta360",
        "use insta360 camera",
        "use the insta360 camera",
        "look at me",
    ]
    active_phrases = [
        "which camera is active",
        "what camera are you using",
        "which camera are you using",
        "what camera is active",
    ]

    if text in active_phrases:
        status = get_camera_roles_status()
        active = status.get("active_camera") or {}
        role = status.get("active_role") or "unknown"
        label = "workbench camera" if role == "workbench" else "face camera" if role == "face" else f"{role} camera"
        if active.get("available"):
            return f"The {label} is active."
        return f"The {label} is selected, but the camera is unavailable."

    role = None
    if text in workbench_phrases:
        role = "workbench"
    elif text in face_phrases:
        role = "face"

    if not role:
        return None

    try:
        status = set_active_camera_role(role)
    except ValueError as error:
        message = str(error)
        if "Logitech" in message:
            return "The Logitech C920 is unavailable."
        if "Insta360" in message:
            return "The Insta360 Link is unavailable."
        return "Camera unavailable."

    active = status.get("active_camera") or {}
    if role == "workbench":
        return "Workbench camera selected." if active.get("available") else "The Logitech C920 is unavailable."
    if role == "face":
        return "Face camera selected." if active.get("available") else "The Insta360 Link is unavailable."
    return f"{role.title()} camera selected."


def _is_docs_request(text: str) -> bool:
    docs_phrases = [
        "jarvis docs",
        "jarvis documentation",
        "show docs",
        "show documentation",
        "where are the docs",
        "where is the documentation",
        "open docs",
        "documentation",
    ]

    return text in docs_phrases


def _is_brain_status_request(text: str) -> bool:
    brain_status_phrases = [
        "brain status",
        "jarvis brain status",
        "brain health",
        "jarvis brain health",
        "how is your brain",
        "brain check",
    ]

    if text in brain_status_phrases:
        return True

    if text.startswith("brain status ") or text.startswith("jarvis brain status "):
        return True

    if "brain status" in text or "brain health" in text:
        return True

    return False


def _extract_after_prefix(command: str, prefix: str) -> str:
    """
    Extract note text using the original command while matching normalized prefixes.

    Works for voice punctuation such as:
    - "Remember this, Marty said..."
    - "Remember this: Marty said..."
    - "Note, Marty said..."
    """
    original = (command or "").strip()
    normalized = normalize_text_for_routing(original)
    normalized_prefix = normalize_text_for_routing(prefix)

    if not normalized.startswith(normalized_prefix):
        return ""

    candidates = [
        prefix,
        prefix.replace(":", ","),
        prefix.replace(":", ""),
    ]

    lower_original = original.lower().strip()

    for candidate in candidates:
        candidate_lower = candidate.lower().strip()
        if lower_original.startswith(candidate_lower):
            return original[len(candidate):].strip(" :,.!?")

    prefix_words = normalized_prefix.split()
    original_words = original.split()
    return " ".join(original_words[len(prefix_words):]).strip(" :,.!?")


def route(command: str) -> str:
    text = normalize_text_for_routing(command)

    if not text:
        return "I didn't hear anything, Marty."

    camera_response = _try_camera_role_command(text)
    if camera_response:
        return camera_response

    if _is_runtime_identity_request(text):
        if "memory system" in text or "memory systems" in text:
            return get_memory_stack_response()

        if "model" in text or "llm" in text:
            return get_model_response()

        if (
            "hardware" in text
            or "system" in text
            or "machine" in text
            or "computer" in text
            or "platform" in text
        ):
            return get_platform_response()

        return get_runtime_identity_response()

    if _is_jarvis_goal_request(text):
        return get_jarvis_goal_response()
    exact_memory_response = _try_exact_memory_question(text)
    if exact_memory_response:
        return exact_memory_response        

    if text in ["semantic memory status", "semantic status", "pgvector status"]:
        return get_semantic_memory_status_response()

    if text in ["show semantic memories", "show semantic memory", "list semantic memories"]:
        return get_recent_semantic_memories_response()
        
    if text in [
        "show memory categories",
        "show semantic categories",
        "memory categories",
        "semantic categories",
    ]:
        return get_semantic_categories_response()

    category_commands = {
        "show cruise memories": "cruise",
        "show cruise memory": "cruise",
        "show hardware memories": "hardware",
        "show hardware memory": "hardware",
        "show preference memories": "preference",
        "show preference memory": "preference",
        "show project memories": "project",
        "show project memory": "project",
        "show test memories": "test",
        "show test memory": "test",
        "show work memories": "work",
        "show work memory": "work",
    }

    if text in category_commands:
        return get_semantic_memories_by_category_response(category_commands[text])   

    if text.startswith("semantic search"):
        query = _extract_after_prefix(command, "semantic search")
        return get_semantic_search_response(query)

    if _is_brain_status_request(text):
        return get_brain_status_response()

    if _is_health_check_request(text):
        return get_health_response()

    if _is_help_request(text):
        return get_help_response()

    if _is_version_request(text):
        return get_version_response()

    if _is_memory_summary_request(text):
        return get_memory_summary_response()

    if _is_docs_request(text):
        return get_docs_response()

    if text.startswith("remember this"):
        note = _extract_after_prefix(command, "remember this")
        return _store_semantic_note(note)

    if text.startswith("remember that"):
        fact = _extract_after_prefix(command, "remember that")

        response = _remember_is_fact(fact)
        if response:
            return response

        return _store_semantic_note(fact)

    if text.startswith("remember"):
        note = _extract_after_prefix(command, "remember")

        response = _remember_is_fact(note)
        if response:
            return response

        return _store_semantic_note(note)

    if text.startswith("note that"):
        note = _extract_after_prefix(command, "note that")
        return _store_semantic_note(note)

    if text.startswith("note"):
        note = _extract_after_prefix(command, "note")
        return _store_semantic_note(note)

    if text.startswith("save this"):
        note = _extract_after_prefix(command, "save this")
        return _store_semantic_note(note)

    if text.startswith("save"):
        note = _extract_after_prefix(command, "save")
        return _store_semantic_note(note)

    if text.startswith("update my ") and " to " in text:
        fact = text[len("update "):].strip()
        key, value = fact.split(" to ", 1)

        key = normalize_key(key)
        value = value.strip().strip(" .!?")

        return update_memory(key, value)

    if text.startswith("forget that "):
        key = text[len("forget that "):].strip()
        key = normalize_key(key)

        return forget(key)

    if (
        text.startswith("what is my ")
        or text.startswith("what s my ")
        or text.startswith("who is my ")
        or text.startswith("who s my ")
        or text.startswith("where is my ")
        or text.startswith("where s my ")
    ):
        key = normalize_key(_clean_question_key(text))

        value = recall(key)
        if value:
            return f"Your {key.replace('my ', '')} is {value}, Marty."

        return f"I don't have your {key.replace('my ', '')} saved yet."

    if text in ["what do you remember", "what do you remember about me"]:
        memories = get_all_memories()

        if not memories:
            return "I don't have any long-term memories saved yet, Marty."

        response = "Here's what I remember, Marty: "
        response += "; ".join([f"{k} is {v}" for k, v in memories.items()])
        return response

    natural_memory_response = _try_natural_memory(command)
    if natural_memory_response:
        return natural_memory_response

    if "time" in text or "date" in text:
        return get_time_response()

    if (
        "system" in text
        or "cpu" in text
        or "disk" in text
        or text in ["status", "system status"]
    ):
        return get_system_response()

    if (
        text in ["hello", "hi", "hey", "hey jarvis", "hello jarvis"]
        or "how are you" in text
    ):
        return get_chat_response(command)

    print("[BRAIN] Falling back to LLM...")
    return get_llm_response(command)
