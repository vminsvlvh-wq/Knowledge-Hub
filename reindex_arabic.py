"""Run once after upgrading the Arabic normalization algorithm. Backs up DB first."""
import os, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings
from app.db import get_db, index_document

def main():
    db = Path(settings.DB_PATH).resolve()
    if not db.is_file():
        raise SystemExit("Database not found: " + str(db))
    backup = db.with_suffix(db.suffix + '.before-arabic-reindex.bak')
    if backup.exists():
        raise SystemExit("Backup already exists: " + str(backup))
    shutil.copy2(db, backup)
    with get_db() as conn:
        docs = [dict(r) for r in conn.execute("SELECT id, workspace_id, content FROM documents WHERE is_archived = 0")]
    for doc in docs:
        index_document(doc['id'], doc['workspace_id'], doc['content'] or '')
    print(f"Reindexed {len(docs)} documents. Backup: {backup}")

if __name__ == '__main__':
    main()
