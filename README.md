**English** · [简体中文](README.zh-CN.md)

# AirliftSilence-ReBuild

Silence the iPhone call-recording start/stop announcements, with an upstream Windows GUI and a reusable **macOS Agent skill**.

This fork adds the workflow used on an iPhone 14 Pro / iOS 18.7.2: device-bound backups, durable recovery copies, device-specific silent audio, readback checks, and a documented way to reapply the change. The user confirmed the result in an actual call on 2026-10-26. Reboot persistence has not been tested. See [validation evidence](docs/VALIDATION.md).

## Use with an Agent

Ask your Agent to clone this repository and read [AGENTS.md](AGENTS.md) and [the skill](skills/iphone-call-silence/SKILL.md):

> Use this repository's iphone-call-silence skill to check my iPhone and, if it matches the validated setup, silence the call-recording announcements with a backup.

To install the skill into Codex while keeping it linked to the clone:

```sh
python3 tools/install_skill.py
```

The installer preserves existing skills and refuses to overwrite a same-named personal skill. Use `--target /your/agent/skills/iphone-call-silence` for another location. If a skill installer copies only the skill folder, keep a full clone too and tell the Agent its path or set `AIRLIFT_REPO`.

## macOS quick start

The guarded Agent workflow currently accepts **iPhone15,2 / iOS 18.7.2 / 22H124** only. This is its real-device evidence boundary, not the full upstream exploit compatibility range. It requires Python 3.12, macOS's Apple private framework and audio tools, and an unlocked, trusted iPhone connected over USB.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/call_silence.py doctor
```

For a phone that still has its original announcements, run each step only after the preceding one succeeds:

```sh
.venv/bin/python -u tools/call_silence.py canary
.venv/bin/python -u tools/call_silence.py backup
.venv/bin/python -u tools/call_silence.py generate
.venv/bin/python -u tools/call_silence.py silence
```

`backup` and `verify` **move files out and back**; they are not read-only. `doctor` does not modify announcement audio. `generate` and `check-files` work only on local files. Keep the phone connected until device operations finish.

If you already used the earlier local wrapper, import its known originals instead of backing up an already-silenced phone. See [the full workflow and migration instructions](docs/AGENT-WORKFLOW.zh-CN.md).

### Reapply after announcements return

With the same phone and original local state, double-click `再次取消录音提示音.command`, or run:

```sh
.venv/bin/python tools/call_silence.py check-files
.venv/bin/python tools/call_silence.py doctor
.venv/bin/python -u tools/call_silence.py silence
```

Both files must report `verified`, and the process must exit successfully. Then confirm with an actual call. Restore the original audio with `restore` or `恢复录音提示音.command`.

All per-device state lives in ignored `.airlift-local/`. It includes originals, hashes, private device identity, pairing cache and recovery snapshots. **Keep it private and backed up.** A different phone or iOS build is rejected. For multiple devices, use a separate `--state-dir` for every command.

## Upstream Windows GUI

The original `airlift_gui.py` remains available on Windows with 64-bit iTunes / Apple Mobile Device Support installed:

```sh
python -m pip install -r requirements.txt
python airlift_gui.py
```

This fork has not newly validated Windows. The upstream author reported iOS 27.0.1 (24A446) testing. Upstream executable releases belong to [AirliftSilence](https://github.com/YiHoooong/AirliftSilence/releases), not to a new binary produced by this fork.

Root `silent/` contains upstream example assets. The Agent workflow generates its own files from the phone's originals and does not use those examples. The low-level `airlift.py` CLI is for research; it does not provide the wrapper's enrollment and local backup-integrity checks.

## Limits and recovery

Only these two files are targeted by the guarded workflow:

- `/var/mobile/Library/CallServices/Greetings/default/StartDisclosureWithTone.m4a`
- `/var/mobile/Library/CallServices/Greetings/default/StopDisclosure.caf`

Periodic reminders during long recordings may remain. iOS can regenerate announcements, so the change is not guaranteed permanent. On any error, stop repeated attempts and preserve both local recovery copies and device Media artifacts; see [failure handling](docs/AGENT-WORKFLOW.zh-CN.md#恢复与失败处理). The tool is based on a real sandbox escape; an interrupted operation can leave files moved or incomplete.

The announcements normally inform both call participants. Obtain any required consent before recording. This project does not place calls or make a permanent change to recording policy.

## Development checks

```sh
python3.12 -m unittest discover -s tests -v
```

Offline guard tests and macOS synthetic AAC/Opus tests never connect to a phone. CI runs them on Linux and macOS; the audio test skips when Core Audio is unavailable.

## Credits

- [airlift](https://github.com/0xjohnnydev/airlift), Johnny Franks — AirTraffic / ATAirlock research and original macOS PoC.
- [airlift-windows](https://github.com/DahanGuy/airlift-windows), Guy Dahan — Windows ctypes port.
- [AirliftSilence](https://github.com/YiHoooong/AirliftSilence), YiHoooong — announcement replacement GUI and Grappa session fix.
- [ios-calltone-silence](https://github.com/jiutinglifeng/ios-calltone-silence), jiutinglifeng — macOS framework loading and device detection fixes, incorporated from commit `67582b82ec6d16d596085bc1cd142ec59350ea10`.
- [AirCard-iOS](https://github.com/Mak5er/AirCard-iOS) — Grappa tokens and protocol work.
- [bl_sbx](https://github.com/h2zi/bl_sbx) — prior announcement replacement work.

MIT. See [LICENSE](LICENSE).
