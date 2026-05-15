import os
import re
import sqlite3
import argparse
from pathlib import Path


class SQLProcedureAnalyzer:
    def __init__(self, db_path=None):
        if db_path is None:
            os.makedirs("output/analysis_dbs", exist_ok=True)
            db_path = "output/analysis_dbs/codebase_index.db"
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._setup_db()

    def _setup_db(self):
        # Table to store procedure dependencies
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sql_dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_path TEXT,
                dependency_name TEXT,
                dependency_type TEXT,
                raw_line TEXT
            )
        """
        )
        # Table for complexity metrics
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sql_metrics (
                path TEXT PRIMARY KEY,
                line_count INTEGER,
                proc_name TEXT,
                crud_operations TEXT,
                complexity_score INTEGER
            )
        """
        )
        self.conn.commit()

    def analyze_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return

        # 1. Extract Dependencies (EXEC, JOIN, FROM, etc)
        # Regex for EXEC [Schema].[Proc] or EXEC Proc
        exec_matches = re.findall(
            r"EXEC(?:UTE)?\s+([\w\.\[\]]+)", content, re.IGNORECASE
        )
        for match in exec_matches:
            self.cursor.execute(
                "INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, raw_line) VALUES (?, ?, ?, ?)",
                (str(file_path), match, "PROCEDURE", f"EXEC {match}"),
            )

        # Regex for Tables (FROM [Schema].[Table], JOIN [Table], etc)
        table_matches = re.findall(
            r"(?:FROM|JOIN|UPDATE|INTO)\s+([\w\.\[\]]+)", content, re.IGNORECASE
        )
        for match in table_matches:
            if match.upper() not in ["SELECT", "INSERT", "UPDATE", "DELETE", "VALUES"]:
                self.cursor.execute(
                    "INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, raw_line) VALUES (?, ?, ?, ?)",
                    (str(file_path), match, "TABLE/VIEW", f"REF {match}"),
                )

        # 2. Extract Metrics & CRUD
        crud = []
        if re.search(r"INSERT\s+INTO", content, re.IGNORECASE):
            crud.append("C")
        if re.search(r"SELECT\s+", content, re.IGNORECASE):
            crud.append("R")
        if re.search(r"UPDATE\s+", content, re.IGNORECASE):
            crud.append("U")
        if re.search(r"DELETE\s+", content, re.IGNORECASE):
            crud.append("D")

        # Simple complexity score: count IF, WHILE, CASE, BEGIN
        complexity = len(
            re.findall(r"\b(IF|WHILE|CASE|BEGIN)\b", content, re.IGNORECASE)
        )

        # Try to find procedure name
        proc_name_match = re.search(
            r"CREATE\s+PROC(?:EDURE)?\s+([\w\.\[\]]+)", content, re.IGNORECASE
        )
        proc_name = (
            proc_name_match.group(1) if proc_name_match else Path(file_path).stem
        )

        self.cursor.execute(
            """
            INSERT OR REPLACE INTO sql_metrics (path, line_count, proc_name, crud_operations, complexity_score)
            VALUES (?, ?, ?, ?, ?)
        """,
            (str(file_path), len(lines), proc_name, "".join(crud), complexity),
        )

    def run_analysis(self, target_dir):
        print(f"Analyzing SQL logic in {target_dir}...")
        files_processed = 0
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".sql"):
                    self.analyze_file(Path(root) / file)
                    files_processed += 1
                    if files_processed % 500 == 0:
                        self.conn.commit()
                        print(f"Processed {files_processed} procedures...")
        self.conn.commit()
        print(f"Finished analysis. Total procedures: {files_processed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze T-SQL stored procedures for dependencies and CRUD logic."
    )
    parser.add_argument("path", help="Path to SQL files")
    parser.add_argument(
        "--db",
        default=None,
        help="SQLite DB to store results (defaults to output/analysis_dbs/codebase_index.db)",
    )

    args = parser.parse_args()
    analyzer = SQLProcedureAnalyzer(args.db)
    analyzer.run_analysis(args.path)
