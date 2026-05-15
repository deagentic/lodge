import os
import hashlib
import sqlite3
import argparse
import re
from pathlib import Path
from datasketch import MinHash


def tokenize(text):
    text = text.lower()
    text = re.sub(r'#.*', '', text)
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'\s+', '', text)
    n = 5
    return [text[i:i+n] for i in range(len(text)-n+1)] if len(text) > n else [text]


class CodeIndexer:
    def __init__(self, db_path=None, num_perm=128):
        if db_path is None:
            os.makedirs("output/analysis_dbs", exist_ok=True)
            db_path = "output/analysis_dbs/codebase_index.db"
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.num_perm = num_perm
        self._setup_db()

    def _setup_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                filename TEXT,
                extension TEXT,
                size INTEGER,
                hash TEXT,
                minhash BLOB,
                project_root TEXT
            )
        """)
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON files(hash)")
        self.conn.commit()

    def get_file_data(self, file_path):
        hasher = hashlib.sha256()
        m = MinHash(num_perm=self.num_perm)
        try:
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
                hasher.update(content_bytes)

                # Fingerprint
                try:
                    text = content_bytes.decode('utf-8', errors='ignore')
                    tokens = tokenize(text)
                    for token in tokens:
                        m.update(token.encode('utf-8'))
                except Exception:  # nosec B110  # best-effort: tokenization optional
                    pass

            return hasher.hexdigest(), m.serialize()
        except Exception:  # nosec B110  # best-effort: file read optional
            return None, None

    def _index_single_file(self, path: Path, file: str, project_name: str) -> bool:
        file_hash, minhash_blob = self.get_file_data(path)
        if not file_hash:
            return False

        try:
            self.cursor.execute("""
                INSERT OR REPLACE INTO files (path, filename, extension, size, hash, minhash, project_root)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(path), file, path.suffix, path.stat().st_size, file_hash, sqlite3.Binary(minhash_blob), project_name))
            return True
        except Exception as e:
            print(f"Error indexing {path}: {e}")
            return False

    def index_directory(self, root_dir, project_name):
        print(f"Indexing {project_name} at {root_dir}...")
        files_indexed = 0

        for root, _, files in os.walk(root_dir):
            for file in files:
                path = Path(root) / file
                if self._index_single_file(path, file, project_name):
                    files_indexed += 1
                    if files_indexed % 1000 == 0:
                        self.conn.commit()
                        print(f"Indexed {files_indexed} files...")

        self.conn.commit()
        print(f"Finished indexing {project_name}. Total files: {files_indexed}")

    def get_duplicate_stats(self):
        self.cursor.execute("""
            SELECT hash, COUNT(*), GROUP_CONCAT(path, '|')
            FROM files
            GROUP BY hash
            HAVING COUNT(*) > 1
        """)
        return self.cursor.fetchall()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index codebase into SQLite for high-speed analysis.")
    parser.add_argument("path", help="Path to index")
    parser.add_argument("--project", default="default", help="Project label")
    parser.add_argument("--db", default=None, help="Database path (defaults to output/analysis_dbs/codebase_index.db)")

    args = parser.parse_args()
    indexer = CodeIndexer(args.db)
    indexer.index_directory(args.path, args.project)
