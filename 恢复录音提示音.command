#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
.venv/bin/python -u tools/call_silence.py doctor
.venv/bin/python -u tools/call_silence.py restore
