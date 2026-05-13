# skills/docs_skill.py


def get_docs_response() -> str:
    return """
Jarvis documentation, Marty:

Main docs:
- Markdown system documentation:
  docs/JARVIS_SYSTEM_DOCUMENTATION.md

- HTML visual architecture:
  docs/jarvis_system_visual.html

Open the HTML visual locally:
  xdg-open docs/jarvis_system_visual.html

Operational startup:
  ./tools/health_check.py
  python3 testbrain.py

Useful Jarvis commands:
- jarvis help
- jarvis health
- jarvis version
- jarvis memory summary
- jarvis docs
""".strip()
