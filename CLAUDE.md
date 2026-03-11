# Punchline

CLI tool that turns Reddit stories into short-form vertical videos (1080x1920 MP4) with script, voiceover, subtitles, and background video. Supports English and Arabic.

## Tech Stack
- Python 3.11+, `uv` package manager
- CLI: `typer` + `rich`
- Reddit: `praw`
- LLM: Gemini via OpenAI-compatible SDK (`openai`)
- TTS: `edge-tts`
- Video: FFmpeg via `ffmpeg-python`
- Config: YAML (`pyyaml`), env vars (`python-dotenv`)
- Storage: SQLite (`sqlite3` stdlib)

## Dev Commands
```bash
uv run punchline fetch          # Fetch Reddit posts
uv run punchline list           # List stored posts
uv run punchline script <id>    # Generate script
uv run punchline voice <id>     # Generate TTS audio
uv run punchline subs <id>      # Generate subtitles
uv run punchline render <id>    # Render final video
uv run punchline auto           # Full pipeline
```

## Project Structure
```
punchline/
├── cli.py              # Typer CLI entry point
├── config.py           # YAML config loader
├── db.py               # SQLite schema + helpers
├── pipeline.py         # Orchestrator chaining all steps
├── scraper/
│   ├── reddit.py       # PRAW-based fetcher
│   └── scorer.py       # Post scoring logic
├── script/
│   └── generator.py    # LLM script generation
├── tts/
│   └── engine.py       # edge-tts wrapper
├── subs/
│   └── generator.py    # Subtitle timing + .ass generation
└── video/
    └── composer.py     # FFmpeg video composition
config/
    settings.yaml       # All configurable defaults
```

## Config
- `config/settings.yaml` — all defaults (reddit, llm, tts, subs, video)
- `.env` — secrets (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, LLM_API_KEY)

## Conventions
- Type hints on all function signatures
- Config accessed via `punchline.config.get("dotted.key")`
- All DB access through `punchline.db.get_conn()`
- Lazy imports in CLI commands to keep startup fast
- Output files: `output/{audio,subs,video}/<post_id>.*`

## Current Status: Sprint 1 (Phases 1-7)
