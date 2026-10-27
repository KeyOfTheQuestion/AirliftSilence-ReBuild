import asyncio
import json
import math
import struct
import subprocess
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import AsyncMock, patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import call_silence as c

DEVICE = {"udid": "test-device-not-real", "product": "iPhone15,2", "version": "18.7.2", "build": "22H124", "lockdown": object()}


class FakeAfc:
    def __init__(self, **kwargs):
        pass

    async def get_file_contents(self, path):
        return b"recovered original"


def backend():
    return types.SimpleNamespace(AfcService=FakeAfc,
                                 _save_books=AsyncMock(return_value=({}, {})),
                                 _cleanup=AsyncMock(), _afc_exists=AsyncMock(return_value=False))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = c.Store(Path(self.temp.name) / "private")
        self.store.bind(DEVICE, create=True)
        self.store.manifest["canary_passed"] = True

    def fill(self):
        for name in c.NAMES:
            item = self.store.manifest["files"].setdefault(name, {})
            for group in ("original", "silent"):
                data = f"{group}-{name}".encode()
                c.durable(self.store.root / group / name, data)
                item[f"{group}_sha256"] = c.sha(data)
        self.store.save()

    def test_profile_cannot_be_reused_for_another_phone_or_build(self):
        for changes in ({"udid": "another-phone"}, {"build": "another-build"}):
            with self.assertRaisesRegex(RuntimeError, "differs"):
                self.store.bind({**DEVICE, **changes})
        self.assertEqual(self.store.manifest["device"]["udid"], DEVICE["udid"])

    def test_missing_second_file_blocks_before_any_backend_load(self):
        self.fill()
        (self.store.root / "silent" / c.NAMES[1]).unlink()
        with patch.object(c, "load_backend") as loader:
            with self.assertRaises(FileNotFoundError):
                c.main(["silence", "--state-dir", str(self.store.root)])
            loader.assert_not_called()

    def test_recovered_bytes_survive_writeback_failure(self):
        a = backend()
        runtime = c.Runtime(a, self.store)
        runtime.current = c.NAMES[0]

        async def failed_read(*args):
            afc = a.AfcService()
            await afc.get_file_contents("airlift-recovered-example")
            raise OSError("simulated writeback failure")

        a._read_file = failed_read
        runtime.dev, runtime.apple = DEVICE, object()
        with self.assertRaisesRegex(OSError, "writeback"):
            asyncio.run(runtime.read(c.NAMES[0]))
        files = list((self.store.root / "recovery").iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), b"recovered original")

    def test_books_restore_mismatch_is_not_reported_as_success(self):
        a = backend()
        c.Runtime(a, self.store)
        with self.assertRaisesRegex(RuntimeError, "Books restore mismatch"):
            asyncio.run(a._cleanup(FakeAfc(), "src", "link", None, {"Books/Books.plist": b"expected"}, {}))

    def test_mismatched_readback_stops_before_second_replacement(self):
        self.fill()
        a = backend()
        a._replace_file = AsyncMock(return_value=b"old")
        runtime = c.Runtime(a, self.store)
        runtime.dev, runtime.apple = DEVICE, object()
        runtime.read = AsyncMock(return_value=b"wrong bytes")
        with self.assertRaisesRegex(RuntimeError, "readback mismatch"):
            asyncio.run(runtime.apply("silence", self.store.check()))
        self.assertEqual(a._replace_file.await_count, 1)
        self.store.check(("original",))

    def test_repeating_backup_never_overwrites_originals(self):
        self.fill()
        runtime = c.Runtime(backend(), self.store)
        runtime.read = AsyncMock(side_effect=AssertionError("must not read or overwrite"))
        before = self.store.check(("original",))
        asyncio.run(runtime.backup())
        self.assertEqual(before, self.store.check(("original",)))
        runtime.read.assert_not_called()

    def test_exclusive_creation_preserves_existing_original(self):
        path = self.store.root / "original" / c.NAMES[0]
        c.durable(path, b"original")
        with self.assertRaises(FileExistsError):
            c.durable(path, b"replacement")
        self.assertEqual(path.read_bytes(), b"original")

    def test_import_checks_all_files_before_copying_and_excludes_pairing(self):
        legacy = Path(self.temp.name) / "legacy"
        old = {"product": DEVICE["product"], "ios": DEVICE["version"], "build": DEVICE["build"], "files": []}
        for name in c.NAMES:
            item = {"file": name}
            for group in ("original", "silent"):
                data = f"{group}-{name}".encode()
                c.durable(legacy / group / name, data)
                item[f"{group}_sha256"] = c.sha(data)
            old["files"].append(item)
        c.durable(legacy / "pairing" / "secret.plist", b"private")
        (legacy / "manifest.json").write_text(json.dumps(old))
        destination = c.Store(Path(self.temp.name) / "imported")
        c.import_legacy(destination, legacy, DEVICE["udid"])
        destination.check()
        self.assertFalse((destination.root / "pairing").exists())
        with self.assertRaisesRegex(RuntimeError, "empty"):
            c.import_legacy(destination, legacy, DEVICE["udid"])

    def test_import_corruption_leaves_destination_empty(self):
        legacy = Path(self.temp.name) / "legacy-bad"
        old = {"product": DEVICE["product"], "ios": DEVICE["version"], "build": DEVICE["build"], "files": []}
        for name in c.NAMES:
            item = {"file": name}
            for group in ("original", "silent"):
                c.durable(legacy / group / name, b"valid")
                item[f"{group}_sha256"] = c.sha(b"valid")
            old["files"].append(item)
        (legacy / "silent" / c.NAMES[1]).write_bytes(b"corrupted")
        (legacy / "manifest.json").write_text(json.dumps(old))
        destination = c.Store(Path(self.temp.name) / "must-stay-empty")
        with self.assertRaisesRegex(RuntimeError, "Legacy integrity"):
            c.import_legacy(destination, legacy, DEVICE["udid"])
        self.assertFalse(destination.root.exists())


@unittest.skipUnless(sys.platform == "darwin" and sys.version_info >= (3, 12) and Path("/usr/bin/afconvert").exists(), "requires Python 3.12+ and macOS Core Audio")
class AudioTests(unittest.TestCase):
    def test_already_silent_backup_is_rejected_without_publishing(self):
        from audio import generate
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = c.Store(root / "private")
            store.bind(DEVICE, create=True)
            for name in c.NAMES:
                wav = root / "zero.wav"
                with wave.open(str(wav), "wb") as w:
                    w.setparams((1, 2, 44100, 44100, "NONE", "not compressed"))
                    w.writeframes(bytes(88200))
                c.durable(store.root / "original" / name, wav.read_bytes())
                store.manifest["files"][name] = {"original_sha256": c.sha(wav.read_bytes())}
            store.save()
            with self.assertRaisesRegex(RuntimeError, "appears silent"):
                generate(store)
            self.assertFalse((store.root / "silent").exists())

    def test_generate_matches_formats_and_decodes_to_silence(self):
        from audio import generate
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = c.Store(root / "private")
            store.bind(DEVICE, create=True)
            for name, rate, codec, fmt in ((c.NAMES[0], 44100, "aac ", "m4af"), (c.NAMES[1], 48000, "opus", "caff")):
                wave_path = root / "tone.wav"
                with wave.open(str(wave_path), "wb") as w:
                    w.setparams((1, 2, rate, rate, "NONE", "not compressed"))
                    w.writeframes(b"".join(struct.pack("<h", int(5000 * math.sin(i * 2 * math.pi * 440 / rate))) for i in range(rate)))
                original = store.root / "original" / name
                original.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["/usr/bin/afconvert", "-f", fmt, "-d", codec, str(wave_path), str(original)], check=True)
                store.manifest["files"][name] = {"original_sha256": c.sha(original.read_bytes())}
            store.save()
            before = store.check(("original",))
            generate(store)
            store.check()
            for item in store.manifest["files"].values():
                self.assertEqual(item["peak_pcm16"], 0)
                self.assertEqual(item["original_frames"], item["silent_frames"])
            generate(store)  # Idempotent local generation preserves existing files.
            self.assertEqual(before, store.check(("original",)))


if __name__ == "__main__":
    unittest.main()
