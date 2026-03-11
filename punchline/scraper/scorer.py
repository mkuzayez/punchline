"""Post scoring logic — ranks posts by viral potential."""

import math

from punchline.db import get_conn
from punchline.scraper.reddit import RedditPost


def compute_score(post: RedditPost) -> float:
    """Score a post based on engagement signals and content quality.

    Factors:
    - Upvotes (log-scaled)
    - Comment-to-upvote ratio (high = controversial/engaging)
    - Upvote ratio (sweet spot around 0.85-0.95)
    - Body length (prefer medium-length stories)
    """
    # Log-scaled upvote score (0-10 range)
    upvote_score = min(math.log1p(post.score) / math.log(10000) * 10, 10)

    # Comment engagement ratio
    if post.score > 0:
        comment_ratio = min(post.num_comments / post.score, 2.0)
    else:
        comment_ratio = 0
    engagement_score = comment_ratio * 3  # 0-6 range

    # Upvote ratio — sweet spot is 0.85-0.95 (divisive = engaging)
    if 0.80 <= post.upvote_ratio <= 0.95:
        ratio_score = 3.0
    elif 0.70 <= post.upvote_ratio < 0.80:
        ratio_score = 2.0
    else:
        ratio_score = 1.0

    # Body length preference (500-2000 chars is sweet spot)
    body_len = len(post.body)
    if 500 <= body_len <= 2000:
        length_score = 3.0
    elif 2000 < body_len <= 3500:
        length_score = 2.0
    else:
        length_score = 1.0

    return upvote_score + engagement_score + ratio_score + length_score


def score_and_store(posts: list[RedditPost]) -> int:
    """Score posts and store them in the database. Returns count of new posts."""
    conn = get_conn()
    new_count = 0

    for post in posts:
        # Skip if already exists
        existing = conn.execute("SELECT id FROM posts WHERE id = ?", (post.id,)).fetchone()
        if existing:
            continue

        score = compute_score(post)
        conn.execute(
            """INSERT INTO posts (id, subreddit, title, body, url, score, upvote_ratio,
                                  num_comments, created_utc, punchline_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                post.id, post.subreddit, post.title, post.body, post.url,
                post.score, post.upvote_ratio, post.num_comments,
                post.created_utc, score,
            ),
        )
        new_count += 1

    conn.commit()
    conn.close()
    return new_count
