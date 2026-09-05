"""
Text-to-speech integration stub for the voice-note pilot.

Not wired into bot.py by default (keeps the core demo dependency-light),
but shows the intended integration point and interface. Swap in ElevenLabs,
Google Cloud TTS, or an open-source engine depending on cost/quality/
bandwidth trade-offs agreed with the team.

Bandwidth note: compress output (e.g. Opus/OGG at a low bitrate, which is
also Telegram's native voice-note format) rather than sending raw WAV —
this matters a lot for basic-phone / low-data users.
"""

import os


def text_to_speech_elevenlabs(text: str, voice_id: str = "default", out_path: str = "reply.ogg") -> str:
    """
    Minimal ElevenLabs TTS call. Requires ELEVENLABS_API_KEY.
    Returns the path to the generated audio file.

    NOTE: this is a stub for integration planning — install `elevenlabs`
    and fill in real error handling before production use.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set.")

    # Example shape only — confirm current ElevenLabs SDK usage before wiring in,
    # since API interfaces change over time.
    #
    # from elevenlabs.client import ElevenLabs
    # client = ElevenLabs(api_key=api_key)
    # audio = client.text_to_speech.convert(voice_id=voice_id, text=text, output_format="ogg_opus_low")
    # with open(out_path, "wb") as f:
    #     for chunk in audio:
    #         f.write(chunk)
    # return out_path

    raise NotImplementedError("Wire up the real ElevenLabs SDK call here before use.")


def speech_to_text_whisper(audio_path: str) -> str:
    """
    Minimal Whisper STT stub for the voice-note *input* side of the pilot.
    """
    # from openai import OpenAI
    # client = OpenAI()
    # with open(audio_path, "rb") as f:
    #     transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
    # return transcript.text
    raise NotImplementedError("Wire up Whisper (local or API) here before use.")
