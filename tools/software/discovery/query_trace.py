import sqlite3
import argparse
import os


def query_trace(db_path, proc_name):
    if not os.path.exists(db_path):
        print(f"Error: Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Use LIKE for fuzzy search
    search_term = f"%{proc_name}%"

    cur.execute(
        """
        SELECT m.proc_name, m.path, m.line_count, m.crud_operations, m.complexity_score, f.hash
        FROM sql_metrics m
        JOIN files f ON m.path = f.path
        WHERE m.proc_name LIKE ?
    """,
        (search_term,),
    )

    results = cur.fetchall()

    if not results:
        print(f"No procedures found matching: {proc_name}")
        return

    print(f"\nFound {len(results)} matches for '{proc_name}':\n")
    print(
        f"{'Procedure Name':<50} | {'Lines':<5} | {'CRUD':<5} | {'Score':<5} | {'File Path'}"
    )
    print("-" * 120)
    for row in results:
        p_name, p_path, l_count, crud, score, f_hash = row
        print(f"{p_name:<50} | {l_count:<5} | {crud:<5} | {score:<5} | {p_path}")

        # Check for clones of this file
        cur.execute(
            "SELECT path FROM files WHERE hash = ? AND path != ?", (f_hash, p_path)
        )
        clones = cur.fetchall()
        if clones:
            print(f"  [!] Found {len(clones)} identical clones of this logic:")
            for c in clones:
                print(f"      -> {c[0]}")
    print("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Trace stored procedures to their source files."
    )
    parser.add_argument("proc", help="Procedure name to search for")
    parser.add_argument(
        "--db",
        default="output/analysis_dbs/codebase_index.db",
        help="Path to SQLite database",
    )

    args = parser.parse_args()
    query_trace(args.db, args.proc)
