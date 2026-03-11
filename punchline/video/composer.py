"""FFmpeg-based video composition — background + audio + subtitle burn-in."""

import glob as glob_mod
import random
import subprocess
from pathlib import Path
from typing import Any

from punchline.config import get
from punchline.db import get_conn

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "video"
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "backgrounds"


def _get_background_video() -> str:
    """Pick a random background video from the assets directory."""
    videos = glob_mod.glob(str(ASSETS_DIR / "*.mp4"))
    if not videos:
        raise FileNotFoundError(
            f"No background videos found in {ASSETS_DIR}. "
            "Add at least one vertical .mp4 file to assets/backgrounds/"
        )
    return random.choice(videos)


def _get_video_duration(path: str) -> float:
    """Get duration of a video file using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def render_video(post_id: str) -> dict[str, Any]:
    """Render the final video for a post."""
    conn = get_conn()

    # Get script
    script = conn.execute(
        "SELECT * FROM scripts WHERE post_id = ? ORDER BY id DESC LIMIT 1",
        (post_id,),
    ).fetchone()
    if not script:
        raise ValueError(f"No script found for post {post_id}")

    # Get voice
    voice = conn.execute(
        "SELECT * FROM voices WHERE script_id = ? ORDER BY id DESC LIMIT 1",
        (script["id"],),
    ).fetchone()
    if not voice:
        raise ValueError(f"No voice found for post {post_id}")

    audio_path = voice["audio_path"]
    audio_duration = voice["duration_sec"]

    # Get subs path
    subs_path = str(Path(__file__).parent.parent.parent / "output" / "subs" / f"{post_id}.ass")
    if not Path(subs_path).exists():
        raise FileNotFoundError(f"Subtitles not found at {subs_path}")

    # Get background video
    bg_path = _get_background_video()
    bg_duration = _get_video_duration(bg_path)

    # Video settings
    width = get("video.width", 1080)
    height = get("video.height", 1920)
    fps = get("video.fps", 30)
    codec = get("video.codec", "libx264")
    crf = get("video.crf", 23)
    preset = get("video.preset", "medium")

    # Output path
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    video_path = str(OUTPUT_DIR / f"{post_id}.mp4")

    # Build FFmpeg command
    # Strategy: loop background if shorter than audio, trim if longer
    # Use -stream_loop for looping, -t for trimming to audio duration
    loop_count = int(audio_duration / bg_duration) + 1 if bg_duration < audio_duration else 0

    cmd = ["ffmpeg", "-y"]

    # Input: background video (with looping if needed)
    if loop_count > 0:
        cmd += ["-stream_loop", str(loop_count)]
    cmd += ["-i", bg_path]

    # Input: audio
    cmd += ["-i", audio_path]

    # Filter: scale to target resolution, burn in subtitles
    # Use ass filter for .ass subtitles
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"fps={fps},"
        f"ass='{subs_path}'[v]"
    )

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", codec,
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(audio_duration),
        "-movflags", "+faststart",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")

    # Store render in DB
    cursor = conn.execute(
        """INSERT INTO renders (post_id, script_id, voice_id, subs_path, video_path, status)
           VALUES (?, ?, ?, ?, ?, 'done')""",
        (post_id, script["id"], voice["id"], subs_path, video_path),
    )
    conn.commit()

    # Update post status
    conn.execute("UPDATE posts SET status = 'rendered' WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

    return {
        "render_id": cursor.lastrowid,
        "video_path": video_path,
    }
