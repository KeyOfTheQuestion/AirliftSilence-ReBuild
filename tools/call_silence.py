#!/usr/bin/env python3
"""Device-bound, durable-backup workflow. Importing this module never connects."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import posixpath
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("StartDisclosureWithTone.m4a", "StopDisclosure.caf")
TARGET = "/var/mobile/Library/CallServices/Greetings/default"
# Evidence for this agent workflow, not a claim about every upstream-supported OS.
VALIDATED = {("iPhone15,2", "18.7.2", "22H124")}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def durable(path, data):
    """Exclusive creation; never replace an original or a recovery copy."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("xb") as f:
        os.chmod(path, 0o600)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "manifest.json"
        self.manifest = json.loads(self.path.read_text()) if self.path.exists() else None
        if self.manifest is not None and self.manifest.get("schema") != 1:
            raise RuntimeError("Unknown state schema; preserve this directory and investigate")

    def save(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        tmp = self.root / f".manifest-{secrets.token_hex(8)}"
        durable(tmp, (json.dumps(self.manifest, indent=2) + "\n").encode())
        os.replace(tmp, self.path)

    def bind(self, device, create=False):
        info = {k: device[k] for k in ("udid", "product", "version", "build")}
        if self.manifest is None:
            if not create:
                raise RuntimeError("No enrolled device: run canary, backup, then generate")
            self.manifest = {"schema": 1, "device": info, "files": {}, "canary_passed": False}
            self.save()
        elif self.manifest["device"] != info:
            raise RuntimeError("Device or iOS build differs from this backup; do not reuse it")

    def check(self, groups=("original", "silent")):
        if not self.manifest:
            raise RuntimeError("No local manifest; run canary and backup first")
        result = {}
        for name in NAMES:
            item = self.manifest["files"].get(name, {})
            for group in groups:
                path = self.root / group / name
                data = path.read_bytes()
                if not data or sha(data) != item.get(f"{group}_sha256"):
                    raise RuntimeError(f"Integrity check failed: {group}/{name}")
                result[group, name] = data
        return result


class Runtime:
    def __init__(self, backend, store):
        self.a, self.store, self.current = backend, store, "canary.bin"
        base_afc = backend.AfcService
        runtime = self

        class DurableAfc(base_afc):
            async def get_file_contents(self, path):
                data = await super().get_file_contents(path)
                leaf = posixpath.basename(path)
                if leaf.startswith(("airlift-recovered-", "airlift-replaced-")):
                    durable(store.root / "recovery" / f"{leaf}-{runtime.current}", data)
                return data

        backend.AfcService = DurableAfc
        save_books, cleanup = backend._save_books, backend._cleanup

        async def snapshot(afc):
            saved, dirs = await save_books(afc)
            snapshot = {"dirs": dirs, "files": {p: v.hex() if v is not None else None for p, v in saved.items()}}
            durable(store.root / "recovery" / f"books-{secrets.token_hex(8)}.json", json.dumps(snapshot).encode())
            return saved, dirs

        async def verified_cleanup(afc, src, link, recovered, saved, dirs):
            await cleanup(afc, src, link, recovered, saved, dirs)
            for path, original in saved.items():
                if original is None:
                    if await backend._afc_exists(afc, path):
                        raise RuntimeError(f"Books cleanup incomplete: {path}")
                elif await afc.get_file_contents(path) != original:
                    raise RuntimeError(f"Books restore mismatch: {path}")
            print(json.dumps({"books_restored": True}), flush=True)

        backend._save_books, backend._cleanup = snapshot, verified_cleanup

    async def connect(self, requested=None, enroll=False, doctor=False):
        a = self.a
        # A profile always selects its own phone, including with several attached.
        expected = self.store.manifest["device"]["udid"] if self.store.manifest else None
        if requested and expected and requested != expected:
            raise RuntimeError("Requested device differs from the enrolled device")
        dev = await a._resolve_device(requested or expected)
        triple = tuple(dev[k] for k in ("product", "version", "build"))
        if triple not in VALIDATED:
            raise RuntimeError(f"Agent workflow not validated for {triple}; no audio changes made")
        if not doctor or self.store.manifest:
            self.store.bind(dev, create=enroll)
        afc = a.AfcService(lockdown=dev["lockdown"])
        await afc.connect()
        leftovers = [n for n in await afc.listdir("/") if n.startswith("airlift-")]
        if leftovers:
            raise RuntimeError(f"Existing airlift artifacts need recovery before retrying: {leftovers}")
        apple = a.AppleCF()
        self.dev, self.afc, self.apple = dev, afc, apple
        print(json.dumps({"connected": True, "product": dev["product"], "version": dev["version"], "build": dev["build"]}), flush=True)

    async def read(self, name):
        self.current = name
        return await self.a._read_file(self.dev["lockdown"], self.apple, self.dev["udid"], f"{TARGET}/{name}")

    async def canary(self):
        a, afc, dev = self.a, self.afc, self.dev
        self.store.manifest["canary_passed"] = False
        self.store.save()
        tok = secrets.token_hex(10)
        src, link, rec = [f"airlift-{x}-{tok}" for x in ("src", "link", "recovered")]
        target = f"/var/tmp/airlift-agent-canary-{tok}.bin"
        data = secrets.token_bytes(64)
        ids = [f"../../{src}/p0/p1/p2/link", f"../../{src}/payload", posixpath.relpath(target, a.AIRLOCK_ROOT)]
        dests = [link, f"{link}/{posixpath.basename(target)}", rec]
        saved, dirs = await a._save_books(afc)
        try:
            await a._stage(dev["lockdown"], afc, src, ids, "/var/tmp", data)
            a._atc_sync(self.apple, dev["udid"], ids, dests)
            result = None
            for _ in range(60):
                try:
                    result = await afc.get_file_contents(rec)
                    break
                except Exception:
                    await asyncio.sleep(0.25)
            if result != data:
                raise RuntimeError("Canary readback failed; call audio was not targeted")
        finally:
            await a._cleanup(afc, src, link, rec, saved, dirs)
        self.store.manifest["canary_passed"] = True
        self.store.save()
        print(json.dumps({"canary_exact_bytes": True}), flush=True)

    async def backup(self):
        if not self.store.manifest.get("canary_passed"):
            raise RuntimeError("Run canary successfully before backing up audio")
        # Validate every existing original before starting any device operation.
        for name in NAMES:
            path = self.store.root / "original" / name
            item = self.store.manifest["files"].get(name, {})
            if path.exists() and sha(path.read_bytes()) != item.get("original_sha256"):
                raise RuntimeError(f"Untracked or changed original; preserve it: {path}")
        for name in NAMES:
            path = self.store.root / "original" / name
            if path.exists():
                continue
            data = await self.read(name)
            if not data:
                raise RuntimeError("Empty original; stopping")
            durable(path, data)
            self.store.manifest["files"][name] = {"original_sha256": sha(data), "original_bytes": len(data)}
            self.store.save()
            print(json.dumps({"backed_up": name, "bytes": len(data), "sha256": sha(data)}), flush=True)

    async def apply(self, mode, files):
        group = "original" if mode == "restore" else "silent"
        for name in NAMES:
            self.current = name
            expected = files[group, name]
            if mode != "verify":
                previous = await self.a._replace_file(self.dev["lockdown"], self.apple, self.dev["udid"], f"{TARGET}/{name}", expected)
                if previous is None:
                    raise RuntimeError("Old file could not be recovered; stop and inspect Media/recovery")
            actual = await self.read(name)
            if actual != expected:
                raise RuntimeError(f"Device readback mismatch: {name}")
            print(json.dumps({"verified": name, "sha256": sha(actual)}), flush=True)


def load_backend(store):
    store.root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(store.root, 0o700)
    os.environ["AIRLIFT_PAIRING_CACHE"] = str(store.root / "pairing")
    sys.path.insert(0, str(ROOT))
    import airlift
    airlift._logging = True
    return airlift


def import_legacy(store, source, udid):
    """Offline migration of the earlier local-only wrapper; never copy pairing data."""
    if store.path.exists() or (store.root.exists() and any(store.root.iterdir())):
        raise RuntimeError("Import requires a new, empty state directory")
    old = json.loads((source / "manifest.json").read_text())
    triple = (old["product"], old["ios"], old["build"])
    if triple not in VALIDATED:
        raise RuntimeError("Legacy profile is outside the validated workflow")
    indexed = {item["file"]: item for item in old["files"]}
    pending = []
    for name in NAMES:
        for group in ("original", "silent"):
            data = (source / group / name).read_bytes()
            if not data or sha(data) != indexed[name][f"{group}_sha256"]:
                raise RuntimeError(f"Legacy integrity check failed: {group}/{name}")
            pending.append((group, name, data))
    store.manifest = {"schema": 1, "device": {"udid": udid, "product": triple[0], "version": triple[1], "build": triple[2]},
                      "canary_passed": False, "files": {name: {} for name in NAMES}}
    for group, name, data in pending:
        durable(store.root / group / name, data)
        store.manifest["files"][name].update({f"{group}_sha256": sha(data), f"{group}_bytes": len(data)})
    store.save()
    store.check()
    print(json.dumps({"imported": True, "phone_connected": False}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="backup/verify also move files out and back; they are NOT read-only. Keep the phone connected until completion.")
    parser.add_argument("command", choices=("doctor", "canary", "backup", "generate", "check-files", "silence", "verify", "restore", "import-legacy"))
    parser.add_argument("--state-dir", type=Path, default=ROOT / ".airlift-local", help="Private per-device state, defaults to <repo>/.airlift-local")
    parser.add_argument("--device", help="Optional UDID for first enrollment; never put it in public logs")
    parser.add_argument("--source", type=Path, help="Legacy local-device directory, for import-legacy only")
    args = parser.parse_args(argv)
    store = Store(args.state_dir)
    if args.command == "import-legacy":
        if not args.source or not args.device:
            parser.error("import-legacy needs --source <local-device> and --device <its UDID>")
        import_legacy(store, args.source.resolve(), args.device)
        return 0
    if args.command == "check-files":
        store.check()
        print(json.dumps({"local_integrity": True}))
        return 0
    if args.command == "generate":
        store.check(("original",))
        from audio import generate
        generate(store)
        return 0
    if sys.platform != "darwin":
        raise RuntimeError("The agent workflow requires macOS; the upstream Windows GUI remains available")
    # Validate ALL files before connecting or replacing either audio file.
    files = None
    if args.command in ("silence", "verify", "restore"):
        groups = ("original",) if args.command == "restore" else ("original", "silent")
        files = store.check(groups)

    async def run():
        runtime = Runtime(load_backend(store), store)
        await runtime.connect(args.device, enroll=args.command == "canary", doctor=args.command == "doctor")
        if args.command == "canary":
            await runtime.canary()
        elif args.command == "backup":
            await runtime.backup()
        elif args.command in ("silence", "verify", "restore"):
            await runtime.apply(args.command, files)
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}. Preserve state and logs; do not blindly retry.", file=sys.stderr)
        raise SystemExit(1)
