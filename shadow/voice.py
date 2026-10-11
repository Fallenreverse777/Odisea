"""Talk to Shadow out loud on your PC.

    python -m shadow.voice          press Enter, then speak
    python -m shadow.voice --wake   hands-free: start sentences with "Shadow ..."

Needs:  pip install -r requirements-voice.txt
Speaking uses your computer's built-in voice (offline). Listening uses Google's
free speech recognition, so it needs internet (no account or key).
"""

import argparse
import re

from .brain import Shadow

WAKE = re.compile(r"^\s*(hey |ok |okay )?shadow\b[\s,.!]*", re.IGNORECASE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice chat with Shadow.")
    parser.add_argument("--wake", action="store_true", help='hands-free: only respond to "Shadow ..."')
    args = parser.parse_args()

    try:
        import pyttsx3
        import speech_recognition as sr
    except ImportError:
        print("Voice needs a few extra packages. Run:\n  pip install -r requirements-voice.txt")
        return

    shadow = Shadow()
    engine = pyttsx3.init()
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.0  # seconds of silence that end a sentence

    def say(text: str) -> None:
        print(f"Shadow: {text}\n")
        engine.say(text.replace("⏰", ""))
        engine.runAndWait()

    def listen(source) -> str | None:
        try:
            audio = recognizer.listen(source, timeout=None if args.wake else 8, phrase_time_limit=15)
            return recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None  # didn't catch any words
        except sr.RequestError:
            say("I can't reach the speech service. Check your internet connection.")
            return None

    try:
        microphone = sr.Microphone()
    except (OSError, AttributeError):
        print("No microphone found. Plug one in (or check PyAudio is installed) and try again.")
        return

    with microphone as source:
        print("Calibrating to your room's noise, stay quiet a second...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        if args.wake:
            say('I\'m listening. Start with "Shadow" when you want me.')
        else:
            say("Ready.")

        while True:
            try:
                if not args.wake:
                    input("Press Enter and speak (Ctrl+C to quit) ")
                    print("Listening...")
                heard = listen(source)
                if not heard:
                    continue

                if args.wake:
                    if not WAKE.match(heard):
                        continue  # not talking to Shadow
                    heard = WAKE.sub("", heard, count=1)
                    if not heard:
                        say("Yes?")
                        heard = listen(source)
                        if not heard:
                            continue

                print(f"You: {heard}")
                if re.fullmatch(r"(goodbye|bye|stop|quit|exit)( shadow)?", heard.strip().lower()):
                    say("Bye for now.")
                    break
                say("".join(shadow.chat(heard, device="voice")))
            except KeyboardInterrupt:
                print()
                break


if __name__ == "__main__":
    main()
