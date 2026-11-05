# Docintel — agent instructions

Care Guide assessment: an API and a web UI that upload business documents, extract invoice fields, validate them, and search them.

The app is complete (all 17 tasks done). Status lives in one file. Do one task, then stop.

## Start

1. Read `NOW.md`.
2. Run `python3 scripts/task.py next --all`.
3. Pick one `ready` task. Run `python3 scripts/task.py handoff <ID>` and follow that prompt.
4. Claim before editing: `python3 scripts/task.py claim <ID> --agent <short-name>`.
5. When the brief's check passes: `python3 scripts/task.py done <ID> --agent <short-name> --note "<one line>"`.

## Do not

- Do not scan the repository, this home directory, or other interview projects.
- Do not re-decide the stack. It is locked in `docs/DECISIONS.md`.
- Do not edit `board.json` or `NOW.md` by hand.
- Do not edit paths outside the brief's "Create or edit" list.
- Do not add a Python dependency that is not already in `pyproject.toml`.
- Do not invent invoice fields, user accounts, or a second database.
- Do not leave a task `in_progress` with an empty note. If you stop early, `block` it.

## If you are blocked

`python3 scripts/task.py block <ID> --agent <short-name> --note "<what failed and what is left>"`

## Status

`python3 scripts/task.py list` prints the board. That is the status.
