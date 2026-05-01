import shutil
import psutil


def get_system_response() -> str:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    return f"CPU is at {cpu} percent, memory is at {memory} percent, and disk usage is {disk} percent."
