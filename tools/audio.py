"""Build silence from each device's own originals using macOS Core Audio."""
import array
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from call_silence import NAMES, durable, sha


def probe(path):
    text = subprocess.check_output(["/usr/bin/afinfo", str(path)], text=True)
    match = re.search(r"Data format:\s+(\d+) ch,\s+(\d+) Hz,\s+([A-Za-z0-9]+)", text)
    if not match:
        raise RuntimeError(f"Unrecognized audio format: {path}")
    return int(match[1]), int(match[2]), match[3]


def convert(source, output, fmt, codec):
    subprocess.run(["/usr/bin/afconvert", "-f", fmt, "-d", codec, str(source), str(output)], check=True, timeout=60)


def generate(store):
    if sys.version_info < (3, 12):
        raise RuntimeError("Audio generation requires Python 3.12+ for WAVE_FORMAT_EXTENSIBLE decoding")
    store.check(("original",))
    with tempfile.TemporaryDirectory(prefix="airlift-audio-") as folder:
        folder = Path(folder)
        pending = []
        for index, name in enumerate(NAMES):
            target = store.root / "silent" / name
            item = store.manifest["files"][name]
            if target.exists():
                if sha(target.read_bytes()) != item.get("silent_sha256"):
                    raise RuntimeError(f"Untracked or changed silent file; preserve it: {target}")
                continue
            source = store.root / "original" / name
            channels, rate, codec = probe(source)
            encoding = {"aac": "aac ", "opus": "opus", "lpcm": "LEI16", "Int16": "LEI16"}.get(codec)
            if encoding is None:
                raise RuntimeError(f"Unsupported original codec: {codec}")
            decoded = folder / f"original-{index}.wav"
            convert(source, decoded, "WAVE", "LEI16")
            with wave.open(str(decoded)) as wave_in:
                frames = wave_in.getnframes()
                if (wave_in.getnchannels(), wave_in.getframerate()) != (channels, rate):
                    raise RuntimeError("Decoded format mismatch")
                source_samples = array.array("h", wave_in.readframes(frames))
                if max(map(abs, source_samples), default=0) <= 1:
                    raise RuntimeError("Backup appears silent; recover a known original instead of re-enrolling")
            if not 0 < frames / rate < 20:
                raise RuntimeError("Unexpected original duration")
            zeros = folder / f"zeros-{index}.wav"
            with wave.open(str(zeros), "wb") as wave_out:
                wave_out.setparams((channels, 2, rate, frames, "NONE", "not compressed"))
                wave_out.writeframes(bytes(frames * channels * 2))
            encoded = folder / name
            convert(zeros, encoded, "m4af" if name.endswith(".m4a") else "caff", encoding)
            actual = probe(encoded)
            if actual[:2] != (channels, rate) or (codec in ("aac", "opus") and actual[2] != codec):
                raise RuntimeError("Silent encoding mismatch")
            check = folder / f"check-{index}.wav"
            convert(encoded, check, "WAVE", "LEI16")
            with wave.open(str(check)) as wave_check:
                actual_frames = wave_check.getnframes()
                samples = array.array("h", wave_check.readframes(actual_frames))
            peak = max(map(abs, samples), default=0)
            if abs(actual_frames - frames) / rate > 0.024 or peak > 1:
                raise RuntimeError("Silent duration or amplitude check failed")
            metadata = {"silent_sha256": sha(encoded.read_bytes()), "silent_bytes": encoded.stat().st_size,
                        "sample_rate": rate, "channels": channels, "codec": actual[2],
                        "original_frames": frames, "silent_frames": actual_frames, "peak_pcm16": peak}
            pending.append((name, encoded.read_bytes(), metadata))
        # Validate both encodings before publishing either one into the profile.
        for name, data, metadata in pending:
            durable(store.root / "silent" / name, data)
            store.manifest["files"][name].update(metadata)
            store.save()
            print(json.dumps({"generated": name, **metadata}), flush=True)
    store.check()
