"""Subtitle generation with estimated timing and .ass output."""

import re
from pathlib import Path
from typing import Any

from punchline.config import get
from punchline.db import get_conn

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "subs"

# Average speech rate: ~150 words per minute = 2.5 words per second
WORDS_PER_SECOND = 2.5


def _split_into_chunks(text: str, max_chars: int = 35) -> list[str]:
    """Split text into display chunks at natural boundaries."""
    # First split by sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks: list[str] = []

    for sentence in sentences:
        words = sentence.split()
        current_chunk: list[str] = []
        current_len = 0

        for word in words:
            word_len = len(word) + (1 if current_chunk else 0)
            if current_len + word_len > max_chars and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_len = len(word)
            else:
                current_chunk.append(word)
                current_len += word_len

        if current_chunk:
            chunks.append(" ".join(current_chunk))

    return chunks


def _estimate_duration(text: str) -> float:
    """Estimate how long it takes to speak a chunk of text."""
    word_count = len(text.split())
    return max(word_count / WORDS_PER_SECOND, 0.4)  # minimum 400ms


def _format_ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp: H:MM:SS.CC"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _generate_ass(chunks: list[str], durations: list[float]) -> str:
    """Generate a complete .ass subtitle file."""
    font = get("subs.font", "Arial Bold")
    fontsize = get("subs.fontsize", 22)
    primary = get("subs.primary_color", "&H00FFFFFF")
    outline = get("subs.outline_color", "&H00000000")
    outline_w = get("subs.outline_width", 3)
    alignment = get("subs.alignment", 2)
    margin_v = get("subs.margin_v", 80)

    header = f"""[Script Info]
Title: Punchline Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{fontsize},{primary},&H000000FF,{outline},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_w},0,{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    current_time = 0.0

    for chunk, duration in zip(chunks, durations):
        start = _format_ass_time(current_time)
        end = _format_ass_time(current_time + duration)
        # Escape special ASS characters
        escaped = chunk.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{escaped}")
        current_time += duration

    return header + "\n".join(events) + "\n"


def generate_subs(post_id: str) -> dict[str, Any]:
    """Generate .ass subtitles for a post's script."""
    conn = get_conn()

    # Get latest script
    script = conn.execute(
        "SELECT * FROM scripts WHERE post_id = ? ORDER BY id DESC LIMIT 1",
        (post_id,),
    ).fetchone()
    if not script:
        raise ValueError(f"No script found for post {post_id}")

    # Get voice duration if available (for timing calibration)
    voice = conn.execute(
        "SELECT * FROM voices WHERE script_id = ? ORDER BY id DESC LIMIT 1",
        (script["id"],),
    ).fetchone()

    max_chars = get("subs.max_chars_per_line", 35)
    full_text = script["full_text"]

    # Split into chunks
    chunks = _split_into_chunks(full_text, max_chars=max_chars)
    durations = [_estimate_duration(chunk) for chunk in chunks]

    # Calibrate to actual audio duration if available
    if voice:
        total_estimated = sum(durations)
        actual_duration = voice["duration_sec"]
        if total_estimated > 0:
            scale = actual_duration / total_estimated
            durations = [d * scale for d in durations]

    # Generate .ass file
    ass_content = _generate_ass(chunks, durations)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    subs_path = str(OUTPUT_DIR / f"{post_id}.ass")
    with open(subs_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    conn.close()

    return {"subs_path": subs_path, "chunk_count": len(chunks)}
