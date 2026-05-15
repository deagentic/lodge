# Agent Directives

## Mandatory Initialization — Every Session, No Exceptions

**Step 1 — Read AGENTS.md**
Read `AGENTS.md` immediately. It is the Supreme Mandate for this project.

**Step 2 — Verify environment**
Check if `.venv` exists. If not, run the bootstrap sequence from AGENTS.md §1.

**Step 3 — Load context file**
Run `git status --porcelain | awk '{print $2}' | head -20`, then apply the routing table in AGENTS.md to load the correct context file.

**Step 4 — GitOps & Commit Policies**
- **Gitflow:** Follow Gitflow (main/staging).
- **Semantic Versioning:** Adhere to Semantic Versioning.
- **Commits:** Use Atomic and Conventional Commits.

Do not proceed until all four steps are complete.
