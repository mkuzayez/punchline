"""edge-tts wrapper for voice generation."""

import asyncio
from pathlib import Path
from typing import Any

import edge_tts

from punchline.config import get
from punchline.db import get_conn

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "audio"


def _build_ssml(hook: str, body: str, cta: str, voice: str, rate: str, pitch: str) -> str:
    """Build SSML with pauses between sections."""
    return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
    <voice name="{voice}">
        <prosody rate="{rate}" pitch="{pitch}">
            {hook}
            <break time="600ms"/>
            {body}
            <break time="400ms"/>
            {cta}
        </prosody>
    </voice>
</speak>"""


async def _generate_audio(text: str, voice: str, rate: str, output_path: str) -> float:
    """Generate audio using edge-tts. Returns duration in seconds."""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)

    # Get duration using ffprobe
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", output_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def generate_voice(post_id: str, lang: str = "en") -> dict[str, Any]:
    """Generate TTS audio for the latest script of a post."""
    conn = get_conn()

    # Get latest script
    script = conn.execute(
        "SELECT * FROM scripts WHERE post_id = ? ORDER BY id DESC LIMIT 1",
        (post_id,),
    ).fetchone()
    if not script:
        raise ValueError(f"No script found for post {post_id}")

    # Select voice
    voice_key = f"tts.voice_{lang}"
    voice_name = get(voice_key, "en-US-AndrewMultilingualNeural")
    rate = get("tts.rate", "+0%")

    # Build text with natural pauses (using periods for edge-tts pacing)
    full_text = f"{script['hook']}... {script['body']}... {script['cta']}"

    # Output path
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = str(OUTPUT_DIR / f"{post_id}.mp3")

    # Generate
    duration = asyncio.run(_generate_audio(full_text, voice_name, rate, audio_path))

    # Store in DB
    cursor = conn.execute(
        "INSERT INTO voices (script_id, audio_path, duration_sec, voice_name) VALUES (?, ?, ?, ?)",
        (script["id"], audio_path, duration, voice_name),
    )
    conn.commit()

    # Update post status
    conn.execute("UPDATE posts SET status = 'voiced' WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

    return {
        "voice_id": cursor.lastrowid,
        "audio_path": audio_path,
        "duration_sec": duration,
        "voice_name": voice_name,
    }
