# tools/regression_test_brain.py

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.brain import think  # noqa: E402


TEST_PROMPTS = [
    "what hardware are you running on",
    "what model are you using",
    "what memory systems do you have",
    "what is the long term goal for Jarvis",
    "what database does Marty prefer",
    "what cruise ship does Marty like",
    "what is my wife's name",
    "where do I work",
    "what do you remember",
    "semantic memory status",
    "brain status",
    "show memory categories",
    "show cruise memories",
    "show project memories",
    "show test memories",
    "show work memories",
]


def main():
    print("===================================")
    print(" Jarvis Brain Regression Test")
    print("===================================")

    for index, prompt in enumerate(TEST_PROMPTS, start=1):
        print()
        print("=" * 80)
        print(f"[{index}] USER: {prompt}")
        print("=" * 80)

        try:
            response = think(prompt)
        except Exception as error:
            response = f"[ERROR] {type(error).__name__}: {error}"

        print(f"JARVIS: {response}")

    print()
    print("===================================")
    print(" Regression test complete")
    print("===================================")


if __name__ == "__main__":
    main()
