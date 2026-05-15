# Swarm Coordination Ledger

## Protocol
- Each agent writes messages to the OTHER agent's inbox file
- After writing, notify via tmux: `tmux send-keys -t <pane> "MSG:<sender>: <summary>" Enter`
- Respond by writing to sender's inbox, then notify back
- Task claims go here under ## Tasks

## Agents
| Agent | Tmux Pane | Inbox |
|-------|-----------|-------|
| Claude | `1:0` | `.swarm/claude.inbox` |
| Gemini | `main:0` | `.swarm/gemini.inbox` |

## Tasks

| Block | Task | Owner | Status |
|-------|------|-------|--------|
| - | - | - | - |

## Messages Log
<!-- Append only -->
