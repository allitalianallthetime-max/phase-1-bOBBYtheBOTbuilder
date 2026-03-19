"""Conception memory — recall prior knowledge, absorb new learnings."""
import httpx
from worker_config import CONCEPTION_URL, internal_headers, log_event, log


async def recall(user_email: str, junk_desc: str, project_type: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{CONCEPTION_URL}/recall",
                json={"user_email": user_email, "junk_desc": junk_desc[:500],
                       "project_type": project_type[:200]},
                headers=internal_headers(),
            )
            if resp.status_code == 200:
                return resp.json().get("context", "")
    except Exception as e:
        log.debug("Conception recall skipped: %s", e)
    return ""


async def absorb(user_email, junk_desc, project_type, blueprint,
                 grok_notes, review_notes, build_id, tokens_used):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{CONCEPTION_URL}/absorb",
                json={
                    "user_email": user_email, "junk_desc": junk_desc[:2000],
                    "project_type": project_type[:500], "blueprint": blueprint[:3000],
                    "grok_notes": grok_notes[:2000], "review_notes": str(review_notes)[:1000],
                    "build_id": build_id, "tokens_used": tokens_used,
                },
                headers=internal_headers(),
            )
    except Exception as e:
        log.debug("Conception absorb failed: %s", e)
