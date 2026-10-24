"""Shared, deterministic identities for reproducible validation studies."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import platform
import re
import subprocess


def parse_seed_range(value):
    """Parse one nonnegative seed or an inclusive ascending seed range."""
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", str(value))
    if match is None:
        raise argparse.ArgumentTypeError("seeds must be N or N-M (nonnegative integers)")
    first = int(match[1])
    last = int(match[2]) if match[2] is not None else first
    if last < first:
        raise argparse.ArgumentTypeError("seed range must be ascending")
    return list(range(first, last + 1))


def source_identity():
    """Identify the actual Python sources, including uncommitted changes.

    Neither wall time nor PYTHONHASHSEED is included: two determinism runs
    should report the same source identity. Their launch commands record the
    distinct hash seeds. The byte digest is also available outside a Git tree.
    """
    root = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root,
            stderr=subprocess.DEVNULL, text=True).strip()
        tracked_changes = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=root,
            stderr=subprocess.DEVNULL, text=True).strip()
        untracked = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "fs_bot"],
            cwd=root, stderr=subprocess.DEVNULL, text=True).split("\0")
        # Writing the first report must not change a later run's identity.
        # Untracked Python still matters: it participates in the byte digest.
        dirty = bool(tracked_changes or any(path.endswith(".py") for path in untracked))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    digest = hashlib.sha256()
    for path in sorted((root / "fs_bot").rglob("*.py")):
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
    return {"commit": commit, "dirty": dirty, "source_sha256": digest.hexdigest()}


def validation_metadata(tool, scenarios, seeds, card_edition, **options):
    """Return settings and source identity shared by a validation run."""
    options.setdefault("python", platform.python_version())
    return dict(metadata_version=1, tool=tool, **source_identity(),
                scenarios=list(scenarios), seeds=list(seeds),
                card_edition=card_edition, **options)
