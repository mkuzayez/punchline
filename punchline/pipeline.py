"""Pipeline orchestrator — chains all steps together."""

from rich.console import Console

console = Console()


def run_pipeline(lang: str = "en", count: int = 1, source: str = "json") -> None:
    """Run the full pipeline: fetch → pick best → script → voice → subs → render."""
    from punchline.db import get_conn
    from punchline.scraper.reddit import fetch_posts
    from punchline.scraper.scorer import score_and_store
    from punchline.script.generator import generate_script
    from punchline.subs.generator import generate_subs
    from punchline.tts.engine import generate_voice
    from punchline.video.composer import render_video

    # Step 1: Fetch
    console.print("[bold cyan]Step 1/6:[/bold cyan] Fetching posts…")
    posts = fetch_posts(source=source)
    stored = score_and_store(posts)
    console.print(f"  {stored} new posts fetched.")

    # Step 2: Pick best unused posts
    conn = get_conn()
    rows = conn.execute(
        "SELECT id FROM posts WHERE status = 'new' ORDER BY punchline_score DESC LIMIT ?",
        (count,),
    ).fetchall()
    conn.close()

    if not rows:
        console.print("[red]No new posts available. Try fetching more.[/red]")
        return

    for i, row in enumerate(rows):
        post_id = row["id"]
        console.print(f"\n[bold]━━━ Video {i + 1}/{len(rows)} ━━━[/bold]")

        # Step 3: Script
        console.print("[bold cyan]Step 2/6:[/bold cyan] Generating script…")
        script_result = generate_script(post_id, lang=lang)
        console.print(f"  Mood: {script_result['mood']}")

        # Step 4: Voice
        console.print("[bold cyan]Step 3/6:[/bold cyan] Generating voice…")
        voice_result = generate_voice(post_id, lang=lang)
        console.print(f"  Duration: {voice_result['duration_sec']:.1f}s")

        # Step 5: Subtitles
        console.print("[bold cyan]Step 4/6:[/bold cyan] Generating subtitles…")
        subs_result = generate_subs(post_id)
        console.print(f"  Subs: {subs_result['subs_path']}")

        # Step 6: Render
        console.print("[bold cyan]Step 5/6:[/bold cyan] Rendering video…")
        render_result = render_video(post_id)
        console.print(f"  [green bold]Done![/green bold] {render_result['video_path']}")

        # Mark post as done
        conn = get_conn()
        conn.execute("UPDATE posts SET status = 'done' WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()
