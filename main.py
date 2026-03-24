from audio.listen import listen_command
from audio.speak import speak
from core.brain import think

USE_WAKE_WORD = False

def main():
    print("Jarvis starting...")
    speak("Jarvis online.")

    while True:
        if USE_WAKE_WORD:
            from audio.listen import listen_for_wake_word

            if not listen_for_wake_word():
                continue
            speak("Yes?")
        else:
            input("\nPress Enter, then speak to Jarvis...")

        command = listen_command().strip()

        if not command:
            print("Jarvis: I didn't catch that.")
            continue

        response = think(command)

        print(f"Jarvis: {response}")
        speak(response)

        if command.lower() in ["exit", "quit"]:
            break

if __name__ == "__main__":
    main()
