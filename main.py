from audio.listen import listen_command
from audio.speak import speak
from core.brain import think

USE_WAKE_WORD = False
EXIT_WORDS = {"exit", "quit", "goodbye", "shutdown"}

def main():
    print("Jarvis starting...")
    speak("Jarvis online.")

    while True:
        try:
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

            print(f"You said: {command}")

            if command.lower() in EXIT_WORDS:
                response = "Goodbye."
                print(f"Jarvis: {response}")
                speak(response)
                break

            response = think(command)

            print(f"Jarvis: {response}")
            speak(response)

        except KeyboardInterrupt:
            print("\nJarvis: Shutting down.")
            speak("Shutting down.")
            break
        except Exception as e:
            print(f"Jarvis error: {e}")
            speak("Something went wrong.")

if __name__ == "__main__":
    main()
