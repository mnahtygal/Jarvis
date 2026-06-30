# Voice Architecture

## Purpose
The voice layer provides hands-free interaction with Jarvis.

## Pipeline
Microphone input → speech-to-text → brain/router → response → text-to-speech.

## Design Rules
- Voice commands should be safe by default
- Destructive actions require confirmation
- Voice should fail gracefully
- Audio device configuration should be documented

## Future Work
- Wake word mode
- Conversation mode
- Better audio diagnostics
