import sqlite3
import unicodedata
import os
from contextlib import contextmanager
from app.config import settings

class PostgreSQLCursor:
    """DB-API style cursor translating the project's SQLite qmark parameters."""
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        # All application SQL uses '?' only as positional parameter markers.
        self._cursor.execute(sql.replace("?", "%s"), params or ())
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class PostgreSQLConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PostgreSQLCursor(self._conn.cursor())

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db_connection(db_path: str = None):
    # Explicit SQLite path overrides DATABASE_URL so unit tests remain isolated.
    database_url = os.getenv('DATABASE_URL', '').strip()
    if db_path is None and database_url:
        if not database_url.startswith(('postgresql://', 'postgres://')):
            raise RuntimeError('DATABASE_URL must be a PostgreSQL URL')
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError('Install psycopg[binary] for PostgreSQL support') from exc
        return PostgreSQLConnection(psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10))
    target_path = db_path or settings.DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn


@contextmanager
def get_db(db_path: str = None):
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str = None):
    postgres = db_path is None and bool(os.getenv('DATABASE_URL', '').strip())
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. Workspaces Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        # 3. Workspace Members & RBAC Roles Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS workspace_members (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner', 'admin', 'editor', 'viewer', 'guest')),
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(workspace_id, user_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        # 4. Documents & Folders Hierarchy Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            parent_id TEXT DEFAULT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            content_type TEXT DEFAULT 'markdown',
            is_archived INTEGER DEFAULT 0,
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES documents(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        # 5. Document Specific Permissions (Override Table)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_permissions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            permission TEXT NOT NULL CHECK(permission IN ('view', 'edit', 'admin')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(document_id, user_id),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        # 6. Document Version History (Snapshots)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            change_summary TEXT DEFAULT '',
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        # 7. Document Chunks for Vector Search & RAG
        cursor.execute(("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        );
        """).replace("BYTEA", "BYTEA" if postgres else "BLOB"))

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_workspace ON document_chunks(workspace_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON document_chunks(document_id);")

        # Knowledge transfer records: isolated by workspace and reviewed before approval.
        cursor.execute("""CREATE TABLE IF NOT EXISTS knowledge_transfers (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
            title TEXT NOT NULL, knowledge_area TEXT NOT NULL, procedure TEXT NOT NULL,
            criticality TEXT NOT NULL CHECK(criticality IN ('low','medium','high')),
            source_document_id TEXT, owner_id TEXT NOT NULL, successor_id TEXT,
            status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','in_review','approved')),
            review_note TEXT NOT NULL DEFAULT '', reviewed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(source_document_id) REFERENCES documents(id) ON DELETE SET NULL,
            FOREIGN KEY(owner_id) REFERENCES users(id),
            FOREIGN KEY(successor_id) REFERENCES users(id),
            FOREIGN KEY(reviewed_by) REFERENCES users(id)
        )""")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_transfer_ws ON knowledge_transfers(workspace_id)')

        # Skills Intelligence: voluntarily entered profiles and admin-set role targets.
        cursor.execute("""CREATE TABLE IF NOT EXISTS role_skill_requirements (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
            role_name TEXT NOT NULL, skill_name TEXT NOT NULL,
            target_level INTEGER NOT NULL CHECK(target_level BETWEEN 1 AND 5),
            UNIQUE(workspace_id,role_name,skill_name),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS skill_profiles (
            workspace_id TEXT NOT NULL, user_id TEXT NOT NULL,
            role_name TEXT NOT NULL, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(workspace_id,user_id),
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS skill_assessments (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, user_id TEXT NOT NULL,
            skill_name TEXT NOT NULL, level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 5),
            evidence_note TEXT NOT NULL DEFAULT '', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(workspace_id,user_id,skill_name),
            FOREIGN KEY(workspace_id,user_id) REFERENCES skill_profiles(workspace_id,user_id) ON DELETE CASCADE
        )""")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_skill_profiles_role ON skill_profiles(workspace_id,role_name)')

        # Decision Impact Tracker: immutable measurements, scoped by workspace.
        cursor.execute("""CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
            problem TEXT NOT NULL, rationale TEXT NOT NULL, alternatives TEXT NOT NULL DEFAULT '',
            owner_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned'
              CHECK(status IN ('planned','active','completed','cancelled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS decision_metrics (
            id TEXT PRIMARY KEY, decision_id TEXT NOT NULL, metric_name TEXT NOT NULL,
            unit TEXT NOT NULL, direction TEXT NOT NULL CHECK(direction IN ('increase','decrease')),
            baseline REAL NOT NULL, target REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(decision_id) REFERENCES decisions(id) ON DELETE CASCADE
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS decision_measurements (
            id TEXT PRIMARY KEY, metric_id TEXT NOT NULL, value REAL NOT NULL,
            note TEXT NOT NULL DEFAULT '', recorded_by TEXT NOT NULL,
            measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(metric_id) REFERENCES decision_metrics(id) ON DELETE CASCADE,
            FOREIGN KEY(recorded_by) REFERENCES users(id)
        )""")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ws ON decisions(workspace_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_metrics_decision ON decision_metrics(decision_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_measurements_metric ON decision_measurements(metric_id)")

        # Indexes for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace_slug ON workspaces(slug);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_members_user ON workspace_members(user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_workspace ON documents(workspace_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_parent ON documents(parent_id);")


# =====================================================================
# AI & RAG ENGINE (Deterministic Vector Space, Semantic Search & Synthesis)
# =====================================================================
import re
import uuid
import hashlib
import numpy as np
from typing import List, Dict, Any

EMBEDDING_DIM = 512

def chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> List[str]:
    if not text or not text.strip():
        return []
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    chunks = []
    current_chunk = []
    current_length = 0
    
    for block in blocks:
        block_len = len(block)
        if current_length + block_len > max_chars and current_chunk:
            combined = "\n\n".join(current_chunk)
            chunks.append(combined)
            if len(combined) > overlap:
                overlap_text = combined[-overlap:].strip()
                current_chunk = [overlap_text, block]
                current_length = len(overlap_text) + block_len
            else:
                current_chunk = [block]
                current_length = block_len
        else:
            current_chunk.append(block)
            current_length += block_len
            
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    return chunks if chunks else [text.strip()]

def normalize_arabic(text: str) -> str:
    """Normalize common Arabic orthographic variants for retrieval only."""
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = re.sub("[أإآٱ]", "ا", text)
    text = text.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return text

def get_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    tokens = re.findall(r'[\w\u0600-\u06FF]+', normalize_arabic(text))
    if not tokens:
        return np.zeros(dim, dtype=np.float32)
    vec = np.zeros(dim, dtype=np.float32)
    stopwords = {'ما', 'هي', 'هو', 'في', 'من', 'علي', 'الي', 'ان', 'عن', 'مع', 'هذا', 'هذه', 'the', 'is', 'at', 'which', 'on', 'and', 'a', 'an'}
    for token in tokens:
        if token in stopwords:
            continue
        h = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16) % dim
        vec[h] += 5.0
        if len(token) >= 3:
            for i in range(len(token) - 2):
                tri = token[i:i+3]
                h_tri = int(hashlib.md5(tri.encode('utf-8')).hexdigest(), 16) % dim
                vec[h_tri] += 0.3
                
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.astype(np.float32)

def index_document(document_id: str, workspace_id: str, content: str):
    chunks = chunk_text(content)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM documents WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        doc_title = row["title"] if row else ""
        
        cursor.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
        for idx, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            embed_input = f"{doc_title}\n\n{chunk}"
            emb = get_embedding(embed_input)
            emb_blob = emb.tobytes()
            cursor.execute("""
                INSERT INTO document_chunks (id, document_id, workspace_id, chunk_index, content, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chunk_id, document_id, workspace_id, idx, chunk, emb_blob))

def semantic_search(
    workspace_id: str,
    query: str,
    allowed_document_ids: List[str],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    if not allowed_document_ids:
        return []
        
    query_vec = get_embedding(query)
    placeholders = ",".join(["?"] * len(allowed_document_ids))
    sql = f"""
        SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding, d.title as doc_title
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.workspace_id = ? AND c.document_id IN ({placeholders}) AND d.is_archived = 0
    """
    params = [workspace_id] + allowed_document_ids
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
    if not rows:
        return []
        
    results = []
    for row in rows:
        emb_chunk = np.frombuffer(row["embedding"], dtype=np.float32)
        score = float(np.dot(query_vec, emb_chunk))
        results.append({
            "chunk_id": row["id"],
            "document_id": row["document_id"],
            "document_title": row["doc_title"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "score": round(max(0.0, score), 4)
        })
        
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def rag_generate_answer(
    workspace_id: str,
    query: str,
    allowed_document_ids: List[str],
    top_k: int = 4
) -> Dict[str, Any]:
    """Evidence-only Corporate Brain MVP: no unsupported generative claims."""
    chunks = semantic_search(workspace_id, query, allowed_document_ids, top_k=top_k)
    # Hashing-based retrieval is a lexical approximation, not an LLM.
    # Require nontrivial overlap and abstain instead of inventing an answer.
    relevant = [chunk for chunk in chunks if chunk["score"] >= 0.08]
    if not relevant:
        return {
            "query": query,
            "answer": "لا توجد أدلة كافية في المستندات المصرح لك بقراءتها. جرّب صياغة أخرى أو اطلب توثيق الموضوع.",
            "citations": [],
            "retrieved_chunks_count": 0
        }

    citations = []
    for idx, chunk in enumerate(relevant, 1):
        citations.append({
            "citation_id": f"[{idx}]",
            "document_id": chunk["document_id"],
            "document_title": chunk["document_title"],
            "snippet": chunk["content"][:500],
            "relevance_score": chunk["score"]
        })

    # Extractive presentation: explicitly label text as source excerpts.
    # This avoids pretending a deterministic similarity algorithm can reason.
    answer = "مقاطع ذات صلة من المستندات المصرح بها (ليست إجابة مولّدة):\n\n"
    answer += "\n\n".join(
        f"[{idx}] {chunk['document_title']}: {chunk['content'][:450]}"
        for idx, chunk in enumerate(relevant[:3], 1)
    )
    return {
        "query": query,
        "answer": answer,
        "citations": citations,
        "retrieved_chunks_count": len(relevant)
    }

def summarize_document(title: str, content: str) -> Dict[str, Any]:
    if not content or not content.strip():
        return {
            "title": title,
            "summary": "المستند فارغ حالياً.",
            "key_takeaways": [],
            "word_count": 0
        }
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    words = content.split()
    headers = [l.lstrip("#").strip() for l in lines if l.startswith("#")]
    bullets = [l.lstrip("-*•").strip() for l in lines if l.startswith(("-", "*", "•"))]
    
    key_points = []
    if bullets:
        key_points = bullets[:5]
    elif headers:
        key_points = headers[:5]
    else:
        sentences = re.split(r'[.؟!]+', content)
        key_points = [s.strip() for s in sentences if len(s.strip()) > 15][:3]
        
    summary_text = (
        f"يقدم هذا المستند المعنون بـ «{title}» دليلاً وتوثيقاً شاملاً يغطي: "
        + (", ".join(key_points[:3]) if key_points else "الموضوعات الموضحة في المتن")
        + "."
    )
    return {
        "title": title,
        "summary": summary_text,
        "key_takeaways": key_points,
        "word_count": len(words)
    }
