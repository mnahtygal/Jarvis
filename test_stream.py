from skills.llm_stream_skill import stream_local_llm


print("Jarvis Streaming Test")
print("---------------------")

prompt = "Explain Flask in one sentence."

print(f"You: {prompt}")
print("Jarvis: ", end="", flush=True)

for chunk in stream_local_llm(prompt):
    print(chunk, end="", flush=True)

print()
