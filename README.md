# Quran Voice Studio v0.1

Mobile-first Streamlit prototype for translated SRT cues to synchronized MP3 using Cartesia TTS.

## Deploy
1. Upload `app.py`, `requirements.txt`, and `packages.txt` to a GitHub repository.
2. Deploy on Streamlit Community Cloud, selecting `app.py`.
3. Enter your Cartesia API key and Voice ID in the app.
4. Upload a translated UTF-8 SRT file.

## Current limitations
- Preserves each cue's original start timestamp.
- Stops if generated speech exceeds its cue duration; it does not silently trim or overlap speech.
- Voice cloning upload, saved voice profiles, automatic voice browsing, and MP4 video export are not included yet.
- Keep API keys private. Configure Streamlit Secrets for a public deployment.
- Cartesia usage consumes credits and follows plan limits.
