"""Distribution version and exact installed-source identity for saved games.

The version identifies the release; the digest also distinguishes development
checkouts and reference changes. It is provenance, not a promise of replay
compatibility between different engine versions.
"""
from functools import lru_cache
import hashlib
from pathlib import Path

__version__ = "0.1.0"


def reference_directory():
    """Locate protected checkout inputs or their unchanged installed copies."""
    package = Path(__file__).resolve().parent
    checkout = package.parent / "Reference Documents"
    return checkout if checkout.is_dir() else package / "_references"


@lru_cache(maxsize=1)
def _engine_identity():
    package = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(package.rglob("*.py")):
        relative = path.relative_to(package)
        if "tests" in relative.parts or "__pycache__" in relative.parts:
            continue
        digest.update(relative.as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    references = reference_directory()
    for path in sorted(references.rglob("*")):
        if path.is_file():
            relative = "references/" + path.relative_to(references).as_posix()
            digest.update(relative.encode("utf-8") + b"\0")
            digest.update(path.read_bytes())
    return {"version": __version__, "source_sha256": digest.hexdigest()}


def engine_identity():
    """Return writer identity without mutating game state or RNG."""
    return dict(_engine_identity())
