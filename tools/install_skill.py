#!/usr/bin/env python3
"""Link the repository skill without replacing any existing personal skill."""
import argparse
import os
from pathlib import Path


def main():
    default_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=default_home / "skills" / "iphone-call-silence")
    args = parser.parse_args()
    target = args.target.expanduser().absolute()
    source = Path(__file__).resolve().parents[1] / "skills" / "iphone-call-silence"
    if target.exists() or target.is_symlink():
        parser.exit(1, f"Preserving existing skill: {target}\nUse another --target, or review the existing skill first.\n")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source, target_is_directory=True)
    print(f"Installed {target} -> {source}")


if __name__ == "__main__":
    main()
