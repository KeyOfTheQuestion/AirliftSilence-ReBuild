#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
.venv/bin/python tools/call_silence.py check-files
if [[ "${1:-}" == "--check-files" ]]; then exit 0; fi
.venv/bin/python -u tools/call_silence.py doctor
mkdir -p .airlift-local/logs
chmod 700 .airlift-local/logs
reapply_log=".airlift-local/logs/reapply-$(date '+%Y%m%d-%H%M%S').log"
.venv/bin/python -u tools/call_silence.py silence 2>&1 | tee "$reapply_log"
echo "文件校验完成，请实际通话试录。日志：$reapply_log"
