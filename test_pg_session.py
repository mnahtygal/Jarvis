from core.session import (
    remember_user_message,
    remember_assistant_message,
    get_recent_history,
    get_context,
)


print("PostgreSQL Conversation History Test")
print("------------------------------------")

remember_user_message("Hello Jarvis, this is a PostgreSQL session test.")
remember_assistant_message("Hello Marty, I saved that to PostgreSQL conversation history.")

print()
print("Recent history:")
for item in get_recent_history():
    print(f"{item['created_at']} | {item['role']}: {item['content']}")

print()
print("Context:")
print(get_context())
