# Agent entry point

For iPhone call-recording announcement tasks, read
`skills/iphone-call-silence/SKILL.md` and `docs/AGENT-WORKFLOW.zh-CN.md`.
Use `tools/call_silence.py` for the guarded macOS workflow.

- Never commit device originals, recovery files, pairing records, UDIDs, local
  manifests or device logs. `.airlift-local/` is private, ignored local state.
- Do not operate a connected phone just to develop or test this repository.
  Run `.venv/bin/python -m unittest discover -s tests -v` with Python 3.12,
  without a phone instead. Core guard tests also run on older Python; the
  Core Audio test then skips.
- `backup` and `verify` move files out and back; they are not read-only operations.
- Preserve existing originals; stop on mismatched identity, integrity errors or
  leftover airlift artifacts. Never remove an OS/build check to force a run.
- Do not change or redirect the user's working legacy checkout automatically.
  Keep its backups and pairing cache in place.
- Keep upstream attribution and distinguish the original Windows GUI from the
  newly guarded macOS agent workflow and its limited validation evidence.
