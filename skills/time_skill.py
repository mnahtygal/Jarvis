from datetime import datetime


def get_time_response() -> str:
    now = datetime.now().strftime("%I:%M %p")
    return f"The time is {now}."
