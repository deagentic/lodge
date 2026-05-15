import sqlite3
import argparse
import os


def print_leaves(db_path, limit=10, max_lines=None):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
    SELECT path, complexity_score, line_count
    FROM sql_metrics
    WHERE path NOT IN (
        SELECT DISTINCT caller_path
        FROM sql_dependencies
        WHERE dependency_type = 'PROCEDURE'
    )
    AND path LIKE '%procedures%'
    """

    if max_lines:
        query += f" AND line_count <= {max_lines}"

    query += f" ORDER BY complexity_score DESC LIMIT {limit};"

    cur.execute(query)
    rows = cur.fetchall()

    print(f"\n--- Top {limit} Complex Leaf Procedures ---")
    if max_lines:
        print(f" (Filtered by max lines: {max_lines})")
    print(f"{'Comp':<5} | {'Lines':<6} | {'Path'}")
    print("-" * 80)
    for row in rows:
        print(f"{row[1]:<5} | {row[2]:<6} | {row[0]}")

    conn.close()


def print_roots(db_path, limit=10):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = (
        f"SELECT caller_path, COUNT(DISTINCT dependency_name) as call_count"  # nosec B608  # query uses internal identifiers only
        f" FROM sql_dependencies"
        f" WHERE dependency_type = 'PROCEDURE'"
        f" GROUP BY caller_path"
        f" ORDER BY call_count DESC"
        f" LIMIT {limit};"
    )

    cur.execute(query)
    rows = cur.fetchall()

    print(f"\n--- Top {limit} Root Procedures (Most Dependencies) ---")
    print(f"{'Calls':<5} | {'Path'}")
    print("-" * 80)
    for row in rows:
        print(f"{row[1]:<5} | {row[0]}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Query SQL topology from the codebase index DB."
    )
    parser.add_argument(
        "--db",
        default="output/analysis_dbs/codebase_index.db",
        help="Path to the SQLite DB.",
    )
    parser.add_argument(
        "--leaves",
        action="store_true",
        help="Show leaf procedures (those that don't call other procedures).",
    )
    parser.add_argument(
        "--roots",
        action="store_true",
        help="Show root procedures (those that call the most other procedures).",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Number of results to return."
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Maximum line count (useful for finding small leaves).",
    )

    args = parser.parse_args()

    if not args.leaves and not args.roots:
        print("Please specify --leaves or --roots. Use -h for help.")

    if args.leaves:
        print_leaves(args.db, args.limit, args.max_lines)

    if args.roots:
        print_roots(args.db, args.limit)
