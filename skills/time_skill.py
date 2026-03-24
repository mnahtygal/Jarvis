from datetime import datetime

def handle(command: str):
    cmd = command.lower().strip()

    if "time" in cmd:
        return datetime.now().strftime("The time is %I:%M %p")

    if "date" in cmd or "day" in cmd:
        return datetime.now().strftime("Today is %A, %B %d, %Y")

    return None
