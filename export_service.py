import os, secrets, json, logging
from io import BytesIO
from contextlib import contextmanager
import psycopg2.pool
from fastapi import FastAPI, Header, Depends, HTTPException
from fastapi.responses import StreamingResponse

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("export_service")

app = FastAPI()

# ── STARTUP GUARDS ──
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError("DATABASE_URL is not set.")

_internal_key = os.getenv("INTERNAL_API_KEY", "")
pool = psycopg2.pool.ThreadedConnectionPool(2, 10, _db_url)


# ── DB CONTEXT MANAGER ──
@contextmanager
def get_db():
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── AUTH ──
def verify(x_internal_key: str = Header(None)):
    if not secrets.compare_digest(x_internal_key or "", _internal_key):
        raise HTTPException(status_code=403, detail="Invalid internal key.")


# ── ENDPOINTS ──

@app.get("/export/vault/{email}", dependencies=[Depends(verify)])
def get_vault(email: str, limit: int = 20):
    """
    Returns all blueprints for a user — the Conception DNA vault.
    Used by the Streamlit UI to populate the 'Load Past Blueprints' panel.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, project_type, blueprint, grok_notes, claude_notes,
                       tokens_used, conception_ready, created_at
                FROM builds
                WHERE user_email = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (email, limit)
            )
            rows = cur.fetchall()

    return {
        "email":  email,
        "count":  len(rows),
        "builds": [
            {
                "id":               r[0],
                "project_type":     r[1],
                "blueprint_preview": r[2][:300] + "..." if r[2] and len(r[2]) > 300 else r[2],
                "tokens_used":      r[5],
                "conception_ready": r[6],
                "created_at":       r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ],
    }


@app.get("/export/blueprint/{build_id}", dependencies=[Depends(verify)])
def get_blueprint(build_id: int):
    """Returns the full blueprint data for a single build."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_email, project_type, blueprint,
                       grok_notes, claude_notes, tokens_used, created_at
                FROM builds WHERE id = %s
                """,
                (build_id,)
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Build {build_id} not found.")

    return {
        "id":           row[0],
        "user_email":   row[1],
        "project_type": row[2],
        "blueprint":    row[3],
        "grok_notes":   row[4],
        "claude_notes": row[5],
        "tokens_used":  row[6],
        "created_at":   row[7].isoformat() if row[7] else None,
    }


@app.get("/export/download/{build_id}", dependencies=[Depends(verify)])
def download_blueprint(build_id: int, fmt: str = "txt"):
    """
    Downloads a blueprint as a plain text or markdown file.
    fmt=txt  → .txt file (default)
    fmt=md   → .md file with section headers

    PDF generation requires reportlab — add to requirements-service.txt
    if you want /download/{id}?fmt=pdf support.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT project_type, blueprint, grok_notes, claude_notes, created_at "
                "FROM builds WHERE id = %s",
                (build_id,)
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Build {build_id} not found.")

    proj, blueprint, grok, claude, created_at = row
    date_str = created_at.strftime("%Y-%m-%d") if created_at else "unknown"
    safe_name = proj.replace(" ", "_").replace("/", "-")[:40]

    if fmt == "md":
        content = f"""# {proj}
*Conception DNA Blueprint — {date_str}*

---

## Synthesis Blueprint

{blueprint}

---

## Mechanical Engineering Notes (Grok)

{grok or 'N/A'}

---

## Systems Architecture Notes (Claude)

{claude or 'N/A'}
"""
        filename    = f"{safe_name}_{build_id}.md"
        media_type  = "text/markdown"

    else:
        content = (
            f"PROJECT: {proj}\n"
            f"DATE: {date_str}\n"
            f"BUILD ID: {build_id}\n"
            f"{'='*60}\n\n"
            f"SYNTHESIS BLUEPRINT\n{'='*60}\n{blueprint}\n\n"
            f"MECHANICAL ENGINEERING (GROK)\n{'='*60}\n{grok or 'N/A'}\n\n"
            f"SYSTEMS ARCHITECTURE (CLAUDE)\n{'='*60}\n{claude or 'N/A'}\n"
        )
        filename   = f"{safe_name}_{build_id}.txt"
        media_type = "text/plain"

    buf = BytesIO(content.encode("utf-8"))
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buf, media_type=media_type, headers=headers)


@app.get("/export/scan/{email}", dependencies=[Depends(verify)])
def get_scans(email: str, limit: int = 20):
    """Returns all equipment vision scans for a user."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, equipment_name, scan_result, created_at
                FROM equipment_scans
                WHERE user_email = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (email, limit)
            )
            rows = cur.fetchall()

    return {
        "email":  email,
        "count":  len(rows),
        "scans":  [
            {
                "id":             r[0],
                "equipment_name": r[1],
                "scan_result":    r[2],
                "created_at":     r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ],
    }


@app.get("/export/stats/{email}", dependencies=[Depends(verify)])
def get_stats(email: str):
    """Conception DNA stats — total builds, tokens consumed, most-built projects."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)              AS total_builds,
                    COALESCE(SUM(tokens_used), 0) AS total_tokens,
                    COUNT(*) FILTER (WHERE conception_ready = TRUE) AS conception_ready_count
                FROM builds WHERE user_email = %s
                """,
                (email,)
            )
            stats = cur.fetchone()

            cur.execute(
                """
                SELECT project_type, COUNT(*) AS n
                FROM builds WHERE user_email = %s
                GROUP BY project_type
                ORDER BY n DESC
                LIMIT 5
                """,
                (email,)
            )
            top_projects = cur.fetchall()

    return {
        "email":                email,
        "total_builds":         stats[0],
        "total_tokens":         stats[1],
        "conception_ready":     stats[2],
        "top_projects":         [{"project": r[0], "count": r[1]} for r in top_projects],
    }


# ── HEALTH ──
@app.get("/health")
def health():
    return {"status": "ok"}
