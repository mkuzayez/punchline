"""Punchline CLI — main entry point."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from punchline.db import init_db

app = typer.Typer(help="Turn Reddit stories into short-form vertical videos.")
console = Console()


def startup() -> None:
    """Initialize DB on first use."""
    init_db()


@app.command()
def fetch(
    lang: str = typer.Option("en", help="Language: en or ar"),
    count: int = typer.Option(25, help="Number of posts to fetch"),
    source: str = typer.Option("json", help="Source: 'json' (no key) or 'praw' (API key)"),
) -> None:
    """Fetch top Reddit stories from configured subreddits and score them."""
    startup()
    from punchline.scraper.reddit import fetch_posts
    from punchline.scraper.scorer import score_and_store

    posts = fetch_posts(count=count, source=source)
    stored = score_and_store(posts)
    console.print(f"[green]Fetched and scored {stored} new posts.[/green]")


@app.command("fetch-url")
def fetch_url(
    url: str = typer.Argument(help="Reddit post URL"),
) -> None:
    """Fetch a single Reddit post by URL (no API key needed)."""
    startup()
    from punchline.scraper.reddit import fetch_post_json
    from punchline.scraper.scorer import score_and_store

    post = fetch_post_json(url)
    stored = score_and_store([post])
    console.print(f"[green]Fetched:[/green] {post.title[:60]}")
    console.print(f"  ID: {post.id} | Score: {post.score} | Comments: {post.num_comments} ({len(post.comments)} fetched)")
    if stored:
        console.print(f"  [green]Stored as new post.[/green]")
    else:
        console.print(f"  [yellow]Already in database.[/yellow]")


@app.command("list")
def list_posts(
    limit: int = typer.Option(10, help="Number of posts to show"),
    status: Optional[str] = typer.Option(None, help="Filter by status"),
) -> None:
    """List stored posts ranked by score."""
    startup()
    from punchline.db import get_conn

    conn = get_conn()
    query = "SELECT id, subreddit, title, punchline_score, status FROM posts"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY punchline_score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    table = Table(title="Posts")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Sub", style="cyan")
    table.add_column("Title", max_width=50)
    table.add_column("Score", justify="right", style="green")
    table.add_column("Status", style="yellow")

    for row in rows:
        table.add_row(
            row["id"][:10] + "…",
            row["subreddit"],
            row["title"][:48],
            f"{row['punchline_score']:.1f}",
            row["status"],
        )
    console.print(table)


@app.command()
def script(
    story_id: str = typer.Argument(help="Post ID to generate script for"),
    lang: str = typer.Option("en", help="Language: en or ar"),
) -> None:
    """Generate a video script from a Reddit story."""
    startup()
    from punchline.script.generator import generate_script

    result = generate_script(story_id, lang=lang)
    console.print(f"[green]Script generated![/green] Mood: {result['mood']}")
    console.print(f"[bold]Hook:[/bold] {result['hook']}")
    console.print(f"[bold]Body:[/bold] {result['body'][:200]}…")
    console.print(f"[bold]CTA:[/bold] {result['cta']}")


@app.command()
def voice(
    story_id: str = typer.Argument(help="Post ID to generate voice for"),
    lang: str = typer.Option("en", help="Language: en or ar"),
) -> None:
    """Generate TTS audio from the script."""
    startup()
    from punchline.tts.engine import generate_voice

    result = generate_voice(story_id, lang=lang)
    console.print(
        f"[green]Voice generated![/green] Duration: {result['duration_sec']:.1f}s"
    )
    console.print(f"Audio: {result['audio_path']}")


@app.command()
def subs(
    story_id: str = typer.Argument(help="Post ID to generate subtitles for"),
) -> None:
    """Generate .ass subtitle file from the script."""
    startup()
    from punchline.subs.generator import generate_subs

    result = generate_subs(story_id)
    console.print(f"[green]Subtitles generated![/green] {result['subs_path']}")


@app.command()
def render(
    story_id: str = typer.Argument(help="Post ID to render video for"),
) -> None:
    """Compose final video with background + audio + subtitles."""
    startup()
    from punchline.video.composer import render_video

    result = render_video(story_id)
    console.print(f"[green]Video rendered![/green] {result['video_path']}")


@app.command()
def auto(
    lang: str = typer.Option("en", help="Language: en or ar"),
    count: int = typer.Option(1, help="Number of videos to produce"),
    source: str = typer.Option("json", help="Source: 'json' (no key) or 'praw' (API key)"),
) -> None:
    """Full pipeline: fetch → pick best → script → voice → subs → render."""
    startup()
    from punchline.pipeline import run_pipeline

    run_pipeline(lang=lang, count=count, source=source)


if __name__ == "__main__":
    app()
