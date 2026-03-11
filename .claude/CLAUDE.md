# Punchline

## What This Is

A fully automated Reddit-to-short-form-video pipeline. Takes Reddit story posts (AITA, TIFU, relationship_advice, etc.), rewrites them into punchy 60-second scripts via LLM, generates voiceover with edge-tts, burns in subtitles, and renders a 1080×1920 MP4 ready for YouTube Shorts, TikTok, or Instagram Reels.

**Core differentiator: Arabic-first.** Most tools in this space are English-only. The Arabic short-form content market is massively underserved relative to its audience — that's the moat. Every step in the pipeline (LLM prompts, TTS voices, subtitle fonts/alignment) has Arabic-specific handling baked in.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| Package manager | `uv` |
| CLI | `typer` + `rich` |
| Reddit | Public JSON API + optional `praw` |
| LLM | Gemini 2.5 Flash Lite via OpenAI-compatible SDK |
| TTS | `edge-tts` (Microsoft Azure Neural voices) |
| Subtitles | Custom `.ass` generator |
| Video | FFmpeg via `subprocess` |
| Config | `pyyaml` + `python-dotenv` |
| Storage | SQLite (WAL mode) |

---

## Project Structure

```
punchline/
├── cli.py              # Typer CLI — all commands, lazy imports for fast startup
├── config.py           # YAML loader, dotted-key access (get("tts.voice_en"))
├── db.py               # SQLite schema (4 tables) + get_conn() helper
├── pipeline.py         # Orchestrator: runs all 6 steps, logs progress via rich
├── scraper/
│   ├── reddit.py       # Fetches posts via public JSON or PRAW; RedditPost dataclass
│   └── scorer.py       # Computes viral potential score (0–13); stores to DB
├── script/
│   └── generator.py    # Gemini LLM → hook/body/cta/mood JSON; EN + AR prompts
├── tts/
│   └── engine.py       # edge-tts async generation; SSML pauses; ffprobe duration
├── subs/
│   └── generator.py    # Splits script → timed chunks; generates .ass subtitle file
└── video/
    └── composer.py     # FFmpeg: loop bg video, overlay audio, burn subs → 1080×1920 MP4
config/
└── settings.yaml       # All defaults (reddit, llm, tts, subs, video)
```

---

## CLI Commands

```bash
uv run punchline fetch [--lang en|ar] [--count 25] [--source json|praw]
uv run punchline fetch-url <reddit-url>
uv run punchline list [--limit 10] [--status new|scripted|voiced|rendered|done]
uv run punchline script <post-id> [--lang en|ar]
uv run punchline voice <post-id> [--lang en|ar]
uv run punchline subs <post-id>
uv run punchline render <post-id>
uv run punchline auto [--lang en|ar] [--count 1] [--source json|praw]
```

`auto` runs the full pipeline end-to-end. Individual commands let you re-run specific steps.

---

## Database Schema

**posts** — Core content store. Status tracks pipeline progress.
- `id` (TEXT PK) — Reddit post ID
- `subreddit, title, body, url`
- `score, upvote_ratio, num_comments, created_utc`
- `punchline_score` (REAL) — Computed viral potential (0–13)
- `status` — `new → scripted → voiced → rendered → done`

**scripts** — LLM output per post.
- FK → `posts.id`, `lang` (en/ar)
- `hook, body, cta, mood, full_text`

**voices** — TTS output per script.
- FK → `scripts.id`
- `audio_path, duration_sec, voice_name`

**renders** — Final video output.
- FKs → `posts.id`, `scripts.id`, `voices.id`
- `subs_path, video_path, status`

All connections use WAL mode + foreign key enforcement via `get_conn()`.

---

## Pipeline Flow

```
fetch_posts()
    → score_and_store()          # punchline_score (log upvotes + engagement + body length)
    → pick top N by score
    → generate_script()          # Gemini: Reddit text → hook/body/cta JSON
    → generate_voice()           # edge-tts SSML → MP3; ffprobe for duration
    → generate_subs()            # split script → chunks → calibrate to audio → .ass
    → render_video()             # FFmpeg: bg loop + audio overlay + subtitle burn
```

Each step updates `posts.status` and stores output in its own DB table.

---

## Scoring Logic

`scorer.py` computes `punchline_score` as a weighted sum:
- `log10(score + 1)` — upvote volume (log-scaled)
- `min(num_comments / score, 1.0) * 3` — comment engagement ratio
- `upvote_ratio * 3` — consensus quality
- `min(body_length / 500, 1.0) * 2` — story length (capped at 500 chars for full score)

Max theoretical score: ~13. Posts are ranked by this before scripting.

---

## LLM Integration

- Provider: Google Gemini via OpenAI-compatible endpoint
- Model: `gemini-2.5-flash-lite` (configurable in `settings.yaml`)
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/openai/`
- Output: JSON with `hook`, `body`, `cta`, `mood` keys
- Language-specific system prompts for EN and AR
- `LLM_API_KEY` env var → Gemini API key

---

## TTS Details

- EN voice: `en-US-AndrewMultilingualNeural`
- AR voice: `ar-SA-HamedNeural`
- Output wrapped in SSML: 600ms pause after hook, 400ms after body
- Duration measured via `ffprobe` after generation
- Subtitle timing calibrated to actual audio duration

---

## Video Output

- Resolution: 1080×1920 (vertical/portrait)
- FPS: 30
- Codec: `libx264`, CRF 23, preset `medium`
- Background: random `.mp4` from `assets/backgrounds/` (user-supplied)
- Subtitles: `.ass` burned in via FFmpeg `subtitles` filter
- Output: `output/video/<post_id>.mp4`

---

## Subtitle Styling (.ass)

- Font: Arial Bold, size 22
- Color: white with black outline (width 3)
- Alignment: bottom-center (alignment=2)
- Margin bottom: 80px
- Max 35 chars per line; split at sentence boundaries

---

## Environment Variables

```
REDDIT_CLIENT_ID=       # PRAW only
REDDIT_CLIENT_SECRET=   # PRAW only
REDDIT_USER_AGENT=      # PRAW only (has hardcoded fallback)
LLM_API_KEY=            # Gemini API key
```

---

## Config Conventions

- All defaults in `config/settings.yaml`
- Access via `punchline.config.get("dotted.key")` anywhere
- CLI commands use lazy imports — startup stays fast regardless of how many deps are installed
- `init_db()` called once on first command execution
