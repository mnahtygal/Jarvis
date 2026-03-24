from skills import time_skill, system_skill, chat_skill

SKILLS = [
    time_skill,
    system_skill,
]

def route(command: str) -> str:
    for skill in SKILLS:
        response = skill.handle(command)
        if response:
            return response

    return chat_skill.handle(command)
