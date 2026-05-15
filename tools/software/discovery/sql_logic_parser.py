import re
import argparse
from pathlib import Path


class SQLLogicParser:
    def __init__(self):
        # Patterns for extraction
        self.patterns = {
            "insert_target": re.compile(r'INSERT\s+INTO\s+([\w\.\[\]]+)', re.IGNORECASE),
            "select_clause": re.compile(r'SELECT\s+(.*?)\s+FROM', re.IGNORECASE | re.DOTALL),
            "where_clause": re.compile(r'WHERE\s+(.*?)($|GROUP|ORDER|HAVING)', re.IGNORECASE | re.DOTALL),
            "joins": re.compile(r'(?:INNER|LEFT|RIGHT|FULL)?\s+JOIN\s+([\w\.\[\]]+)\s+ON\s+(.*?)(?=INNER|LEFT|RIGHT|FULL|JOIN|WHERE|GROUP|ORDER|$)', re.IGNORECASE | re.DOTALL),
            "case_logic": re.compile(r'(CASE\s+.*?END)', re.IGNORECASE | re.DOTALL),
            "math_ops": re.compile(r'([\w\.\[\]]+\s*[\+\-\*/]\s*[\w\.\[\]]+)', re.IGNORECASE)
        }

    def parse(self, sql_content):
        logic = {
            "target": None,
            "fields": [],
            "filters": [],
            "joins": [],
            "complex_logic": []
        }

        # 1. Target Table
        target_match = self.patterns["insert_target"].search(sql_content)
        if target_match:
            logic["target"] = target_match.group(1)

        # 2. Joins
        join_matches = self.patterns["joins"].findall(sql_content)
        for table, condition in join_matches:
            logic["joins"].append({"table": table.strip(), "on": condition.strip()})

        # 3. Filters (Business Rules)
        where_match = self.patterns["where_clause"].search(sql_content)
        if where_match:
            # Clean up the where clause
            raw_filters = where_match.group(1).strip()
            # Split by AND/OR while preserving context (simplistic)
            logic["filters"] = [f.strip() for f in re.split(r'\bAND\b|\bOR\b', raw_filters, flags=re.IGNORECASE)]

        # 4. Complex Transformations (CASE, Math)
        logic["complex_logic"] = [c.strip() for c in self.patterns["case_logic"].findall(sql_content)]

        return logic

    def generate_spec(self, proc_name, logic):
        spec = f"# Logic Specification: {proc_name}\n\n"
        spec += "## 1. Objective\n"
        spec += f"Ingest and transform data into `{logic['target'] or 'Result Set'}`.\n\n"

        if logic["joins"]:
            spec += "## 2. Data Sources & Joins\n"
            for j in logic["joins"]:
                spec += f"- **Join `{j['table']}`**: ON {j['on']}\n"
            spec += "\n"

        if logic["filters"]:
            spec += "## 3. Business Rules (Filters)\n"
            for f in logic["filters"]:
                spec += f"- **Rule**: `{f}`\n"
            spec += "\n"

        if logic["complex_logic"]:
            spec += "## 4. Transformation Logic\n"
            for c in logic["complex_logic"]:
                spec += "### Transformation Rule\n"
                spec += f"```sql\n{c}\n```\n"

        return spec


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    args = parser.parse_args()

    with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        p = SQLLogicParser()
        logic = p.parse(content)
        print(p.generate_spec(Path(args.file).stem, logic))
