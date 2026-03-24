import os

def handle(command: str):
    cmd = command.lower().strip()

    if "status" in cmd:
        return "All systems are operational."

    if "cpu" in cmd:
        output = os.popen("top -bn1 | grep 'Cpu(s)'").read().strip()
        return output if output else "I could not read CPU usage."

    if "memory" in cmd or "ram" in cmd:
        output = os.popen("free -h").read().strip()
        return output if output else "I could not read memory usage."

    if "disk" in cmd or "storage" in cmd:
        output = os.popen("df -h /").read().strip()
        return output if output else "I could not read disk usage."

    return None
