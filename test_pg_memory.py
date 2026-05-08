from core.memory import remember, recall, update_memory, forget, get_all_memories, build_memory_context


print("PostgreSQL Memory Test")
print("----------------------")

print(remember("test fact", "PostgreSQL is working"))
print("Recall:", recall("test fact"))

print(update_memory("test fact", "PostgreSQL memory is working great"))
print("Recall:", recall("test fact"))

print()
print("All memories:")
print(get_all_memories())

print()
print("Memory context:")
print(build_memory_context())

print()
print(forget("test fact"))
