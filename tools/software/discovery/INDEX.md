# Software Discovery Tools

This directory contains the baseline, general-purpose software analysis tools bundled with the Agentic CI template. These tools are designed to work across any codebase to extract structure, detect languages, and map API usages without hardcoded domain specifics.

**Any project-specific findings (like a custom hardware protocol byte or proprietary string) extracted by these tools must be logged into `docs/knowledge/` and NEVER hardcoded into these tools.**

## Baseline Tools Included

- **`main.py`**: The universal codebase analysis wrapper (Retro-engineer). Use this to generate a comprehensive execution graph and software map. Outputs markdown, JSON, or Graphviz dot files.
- **`language_detector.py`**: Detects primary languages and build systems without executing code.
- **`structure_mapper.py`**: Maps module boundaries, classes, and entry points.
- **`call_tree.py`**: Builds an execution graph linking entry points to core APIs.
- **`api_mapper.py`**: Maps external system API calls across the codebase.
- **`decision_extractor.py`**: Parses hardcoded constants, FIXME/TODO comments, and explicit architectural choices.
- **`reporter.py`**: Synthesizes output from the above modules into JSON or Markdown.
- **`sql_procedure_analyzer.py`**: Analyzes T-SQL stored procedures to build a dependency database (`codebase_index.db`).
- **`sql_topology.py`**: Generalizable Python utility to query `codebase_index.db` for architectural topology (e.g. root and leaf procedures).
- **`sql_logic_parser.py`**: Extracts fields, filters, and complex transformations from SQL logic to generate markdown specifications.

*If you encounter a new language or stack not supported by these baseline tools, invoke the **Tool Writer Agent** to augment these tools defensively.*
