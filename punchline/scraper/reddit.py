"""Reddit post fetcher — supports both PRAW (API key) and public JSON (no key)."""

import os
import re
import time
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

from punchline.config import get

load_dotenv()

USER_AGENT = "punchline:v0.1 (short-form video tool)"


@dataclass
class RedditPost:
    id: str
    subreddit: str
    title: str
    body: str
    url: str
    score: int
    upvote_ratio: float
    num_comments: int
    created_utc: float
    comments: list[str] = field(default_factory=list)


# ── Public JSON approach (no API key needed) ──────────────────────────


def _json_headers() -> dict[str, str]:
    return {"User-Agent": USER_AGENT}


def fetch_post_json(url: str) -> RedditPost:
    """Fetch a single post + top comments from a Reddit URL using public JSON."""
    # Normalize URL: strip trailing slash, ensure no query params, add .json
    url = url.split("?")[0].rstrip("/")
    if not url.endswith(".json"):
        url += ".json"

    resp = requests.get(url, headers=_json_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # data[0] = post listing, data[1] = comments listing
    post_data = data[0]["data"]["children"][0]["data"]

    # Extract top-level comments
    comments: list[str] = []
    if len(data) > 1:
        for child in data[1]["data"]["children"]:
            if child["kind"] == "t1":
                body = child["data"].get("body", "")
                if body and len(body) > 20:
                    comments.append(body)

    return RedditPost(
        id=post_data["id"],
        subreddit=post_data["subreddit"],
        title=post_data["title"],
        body=post_data["selftext"],
        url=f"https://reddit.com{post_data['permalink']}",
        score=post_data.get("score", 0),
        upvote_ratio=post_data.get("upvote_ratio", 0),
        num_comments=post_data.get("num_comments", 0),
        created_utc=post_data.get("created_utc", 0),
        comments=comments[:20],  # keep top 20
    )


def fetch_subreddit_json(subreddit: str, sort: str = "hot", limit: int = 25) -> list[RedditPost]:
    """Fetch posts from a subreddit using public JSON."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    resp = requests.get(url, headers=_json_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    min_len = get("reddit.min_body_length", 200)
    max_len = get("reddit.max_body_length", 5000)

    posts: list[RedditPost] = []
    for child in data["data"]["children"]:
        d = child["data"]
        body = d.get("selftext", "")
        if not body or len(body) < min_len or len(body) > max_len:
            continue
        if d.get("over_18", False):
            continue

        posts.append(RedditPost(
            id=d["id"],
            subreddit=subreddit,
            title=d["title"],
            body=body,
            url=f"https://reddit.com{d['permalink']}",
            score=d.get("score", 0),
            upvote_ratio=d.get("upvote_ratio", 0),
            num_comments=d.get("num_comments", 0),
            created_utc=d.get("created_utc", 0),
        ))

    return posts


def fetch_posts_json(count: int = 25) -> list[RedditPost]:
    """Fetch posts from all configured subreddits using public JSON."""
    subreddits = get("reddit.subreddits", ["AmItheAsshole", "tifu"])
    sort = get("reddit.sort", "hot")
    limit = get("reddit.limit", count)

    posts: list[RedditPost] = []
    for sub in subreddits:
        posts.extend(fetch_subreddit_json(sub, sort=sort, limit=limit))
        time.sleep(1)  # be nice to Reddit's rate limit

    return posts[:count]


# ── PRAW approach (requires API key) ─────────────────────────────────


def _get_reddit():
    import praw
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", USER_AGENT),
    )


def fetch_posts_praw(count: int = 25) -> list[RedditPost]:
    """Fetch posts from configured subreddits using PRAW (requires API key)."""
    reddit = _get_reddit()
    subreddits = get("reddit.subreddits", ["AmItheAsshole", "tifu"])
    sort = get("reddit.sort", "hot")
    min_len = get("reddit.min_body_length", 200)
    max_len = get("reddit.max_body_length", 5000)
    limit = get("reddit.limit", count)

    posts: list[RedditPost] = []
    for sub_name in subreddits:
        subreddit = reddit.subreddit(sub_name)
        listing = getattr(subreddit, sort)(limit=limit)

        for submission in listing:
            body = submission.selftext
            if not body or len(body) < min_len or len(body) > max_len:
                continue
            if submission.over_18:
                continue

            posts.append(RedditPost(
                id=submission.id,
                subreddit=sub_name,
                title=submission.title,
                body=body,
                url=f"https://reddit.com{submission.permalink}",
                score=submission.score,
                upvote_ratio=submission.upvote_ratio,
                num_comments=submission.num_comments,
                created_utc=submission.created_utc,
            ))

    return posts[:count]


# ── Unified fetch function ───────────────────────────────────────────


def fetch_posts(count: int = 25, source: str = "json") -> list[RedditPost]:
    """Fetch posts using the chosen source: 'json' (no key) or 'praw' (API key)."""
    if source == "praw":
        return fetch_posts_praw(count=count)
    return fetch_posts_json(count=count)
