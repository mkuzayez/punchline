"""LLM-based script generator using OpenAI-compatible API."""

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from punchline.config import get
from punchline.db import get_conn

load_dotenv()

PROMPT_EN = """You are a viral short-form video scriptwriter. Turn this Reddit story into a 30-60 second video script.

RULES:
- Hook (1-2 sentences): Must grab attention in the first 3 seconds. Use shock, curiosity, or relatability.
- Body (main narrative): Retell the story in a conversational, dramatic tone. Keep it concise. Use short punchy sentences.
- CTA (1 sentence): End with a question or call-to-action to drive comments.
- Mood: One word describing the overall tone (dramatic, funny, wholesome, shocking, heartwarming, infuriating).

OUTPUT FORMAT (strict JSON):
{{
  "hook": "...",
  "body": "...",
  "cta": "...",
  "mood": "..."
}}

REDDIT STORY:
Title: {title}

{body}"""

PROMPT_AR = """أنت كاتب سكريبت لفيديوهات قصيرة فيروسية. حوّل هذه القصة من ريديت إلى سكريبت فيديو مدته 30-60 ثانية.

القواعد:
- الخطاف (جملة أو جملتين): يجب أن يجذب الانتباه في أول 3 ثوانٍ.
- المتن (السرد الرئيسي): أعد سرد القصة بأسلوب محادثة درامي. اجعلها مختصرة.
- الدعوة للتفاعل (جملة واحدة): اختم بسؤال أو دعوة للتعليق.
- المزاج: كلمة واحدة تصف النبرة العامة.

صيغة الإخراج (JSON صارم):
{{
  "hook": "...",
  "body": "...",
  "cta": "...",
  "mood": "..."
}}

قصة ريديت:
العنوان: {title}

{body}"""


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=get("llm.base_url", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    )


def generate_script(post_id: str, lang: str = "en") -> dict[str, Any]:
    """Generate a video script for a given post ID."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not row:
        raise ValueError(f"Post {post_id} not found in database")

    prompt_template = PROMPT_AR if lang == "ar" else PROMPT_EN
    prompt = prompt_template.format(title=row["title"], body=row["body"])

    client = _get_client()
    model = get("llm.model", "gemini-2.5-flash-lite-preview-06-17")

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=get("llm.max_tokens", 1024),
        temperature=get("llm.temperature", 0.7),
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    result = json.loads(raw)

    # Build full text for TTS
    full_text = f"{result['hook']}\n\n{result['body']}\n\n{result['cta']}"

    # Store in DB
    cursor = conn.execute(
        """INSERT INTO scripts (post_id, lang, hook, body, cta, mood, full_text)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (post_id, lang, result["hook"], result["body"], result["cta"], result["mood"], full_text),
    )
    conn.commit()

    # Update post status
    conn.execute("UPDATE posts SET status = 'scripted' WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()

    result["script_id"] = cursor.lastrowid
    result["full_text"] = full_text
    return result
