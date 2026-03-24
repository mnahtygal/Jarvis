from core.router import route

def think(command: str) -> str:
    return route(command)
