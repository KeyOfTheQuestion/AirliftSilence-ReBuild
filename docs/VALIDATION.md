# Validation evidence

## Real-device baseline: 2026-10-26

- iPhone 14 Pro (`iPhone15,2`), iOS 18.7.2 (`22H124`).
- Apple Silicon Mac, macOS 15.0.1 (`24A348`), Python 3.12.13,
  `pymobiledevice3==11.32.0`.
- A disposable canary completed a byte-for-byte round trip.
- Both originals were saved before replacement. Replacement files matched codec,
  sample rate, channels and decoded sample count; decoded PCM peak was zero.
- Both device readbacks matched the replacement SHA-256 values.
- Books indexes were restored and compared; final Media scan found no airlift
  leftovers.
- The user then made an actual test call and confirmed that the announcement
  was gone.

| File | Original bytes | Silent bytes | Decoded duration |
|---|---:|---:|---:|
| StartDisclosureWithTone.m4a | 46670 | 4384 | 1.618639 s |
| StopDisclosure.caf | 44280 | 4387 | 1.920000 s |

This baseline used the earlier local wrapper and the macOS port at
`jiutinglifeng/ios-calltone-silence@67582b82ec6d16d596085bc1cd142ec59350ea10`.
The portable CLI in this fork was extracted and hardened from that workflow;
it has **not** been re-run against the phone as part of repository development.
Do not label offline tests as a new device test.

Reboot persistence, long-recording periodic reminders, other iOS builds and
other models were not tested. Original restoration was not exercised during
this session; its path has offline guard coverage, not a new device result.

## Repository checks

2026-10-27: all 11 tests passed locally with Python 3.12.13 on the Mac above,
including both synthetic Core Audio tests. Skill format, launcher syntax,
installer overwrite protection and README local links were also checked.
No connected-device operation was run for these checks.

Run with Python 3.12:

```sh
python3.12 -m unittest discover -s tests -v
python3.12 -m compileall -q airlift.py tools tests
bash -n 再次取消录音提示音.command 恢复录音提示音.command
```

Tests cover wrong-device/build rejection, full local preflight before backend
load, preservation of recovered bytes when writeback fails, cleanup mismatch
errors, stopping on readback mismatch, exclusive original creation, repeated
backup preservation, corrupt-import rejection, and migration without pairing data.
The macOS tests reject already-silent originals and use
synthetic AAC/Opus audio and checks generated silence; it never connects to a
phone. Other platforms or older Python skip that Core Audio test.

The GitHub workflow runs only these offline checks. Device originals, UDIDs,
pairing records, and raw operation logs are intentionally excluded from this
public evidence.
