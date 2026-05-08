import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = os.path.join(os.path.expanduser("~"), ".clipboard_history", "history.db")
MAX_UNPINNED = 500


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL DEFAULT 'text',
            text_content TEXT,
            image_hash TEXT,
            image_data BLOB,
            pinned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pinned ON clips(pinned)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON clips(created_at)")
    conn.commit()
    conn.close()


def insert_clip(content_type: str, text_content: Optional[str] = None,
                image_data: Optional[bytes] = None) -> int:
    image_hash = None
    if image_data is not None:
        image_hash = hashlib.sha256(image_data).hexdigest()
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO clips (content_type, text_content, image_hash, image_data, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (content_type, text_content, image_hash, image_data,
         datetime.now().isoformat()),
    )
    row_id = cur.lastrowid
    _cleanup(conn)
    conn.commit()
    conn.close()
    return row_id


def _cleanup(conn: sqlite3.Connection):
    pinned_count = conn.execute(
        "SELECT COUNT(*) FROM clips WHERE pinned=1"
    ).fetchone()[0]
    unpinned = conn.execute(
        "SELECT id FROM clips WHERE pinned=0 ORDER BY created_at DESC"
    ).fetchall()
    excess = len(unpinned) - MAX_UNPINNED
    if excess > 0:
        ids_to_del = [row["id"] for row in unpinned[MAX_UNPINNED:]]
        conn.execute(
            f"DELETE FROM clips WHERE id IN ({','.join('?' * len(ids_to_del))})",
            ids_to_del,
        )


def get_clips(search: str = "") -> List[Dict]:
    conn = _get_conn()
    if search:
        rows = conn.execute(
            "SELECT id, content_type, text_content, image_hash, pinned, created_at "
            "FROM clips WHERE text_content LIKE ? "
            "ORDER BY pinned DESC, created_at DESC",
            (f"%{search}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, content_type, text_content, image_hash, pinned, created_at "
            "FROM clips ORDER BY pinned DESC, created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_clip_image(clip_id: int) -> Optional[bytes]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT image_data FROM clips WHERE id=?", (clip_id,)
    ).fetchone()
    conn.close()
    if row:
        return row["image_data"]
    return None


def toggle_pin(clip_id: int) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT pinned FROM clips WHERE id=?", (clip_id,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    new_val = 0 if row["pinned"] else 1
    conn.execute("UPDATE clips SET pinned=? WHERE id=?", (new_val, clip_id))
    conn.commit()
    conn.close()
    return bool(new_val)


def delete_clip(clip_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM clips WHERE id=?", (clip_id,))
    conn.commit()
    conn.close()


def get_clip_text(clip_id: int) -> Optional[str]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT text_content FROM clips WHERE id=?", (clip_id,)
    ).fetchone()
    conn.close()
    if row:
        return row["text_content"]
    return None
