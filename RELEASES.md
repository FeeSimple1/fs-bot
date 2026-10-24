# Local installation and release maintenance

The distribution is named `falling-sky-bot`; its initial package version is
`0.1.0`. This repository supports local installation and builds. Adding this
packaging does not publish a package, create a GitHub release, or certify
complete rules compliance. See [current status](docs/current-status.md) and
[the changelog](CHANGELOG.md) for scope and remaining questions.

## Install and play

Use Python 3.10 or newer. From the checkout, create and activate an environment:

```sh
python -m venv .venv
```

| Shell | Activation command |
|---|---|
| macOS/Linux bash | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.venv\Scripts\activate.bat` |

Then install and launch:

```sh
python -m pip install .
fs-bot --save autosave.json
```

`python -m fs_bot` remains available. Gameplay has no third-party runtime
dependencies. Building a distribution uses setuptools and wheel; running the
development tests uses the separately listed test dependencies.

## Build and check a distribution

From a clean checkout of the revision being evaluated:

```sh
python -m pip install build
python -m build
```

The default build creates a source archive and then builds the wheel from
that archive, checking that required files were included. Use a fresh output
directory when retaining evidence from multiple revisions.

`setup.py` copies the unchanged supplied `Reference Documents` into the
wheel's `fs_bot/_references` directory at build time. The repository keeps
one authoritative source copy. Installed card displays and the citation
utility read those bundled inputs; the balance tool also includes its JSON
baseline. No rules references are edited by the build.

The following check creates a fresh environment, installs a local wheel
without dependencies or an index, and exercises it outside the checkout:

```python
from pathlib import Path
import os
import subprocess
import tempfile
import venv

root = Path.cwd()
wheels = list((root / "dist").glob("*.whl"))
assert len(wheels) == 1, "Use a directory containing only the wheel being checked"
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    venv.EnvBuilder(with_pip=True).create(directory / "env")
    python = directory / "env" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "--no-index",
                    "--no-deps", str(wheels[0])], check=True, cwd=directory)
    subprocess.run([str(python), "-I", str(root / "scripts/smoke_installed.py")],
                   check=True, cwd=directory)
```

The smoke check verifies both launch commands, every card's display text,
the rules chapters, all five scenario setups and save/load, and completed
base-game and Ariovistus bot games. The
[package workflow](.github/workflows/package.yml) runs this check on Linux,
Windows, and macOS and retains the build artifacts. A configured workflow
is not evidence of a successful run; inspect the results for the exact commit.

To verify that a wheel contains byte-identical reference inputs:

```python
from pathlib import Path
import zipfile

source = Path("Reference Documents")
wheels = list(Path("dist").glob("*.whl"))
assert len(wheels) == 1
with zipfile.ZipFile(wheels[0]) as wheel:
    for path in source.rglob("*"):
        if path.is_file():
            name = "fs_bot/_references/" + path.relative_to(source).as_posix()
            assert wheel.read(name) == path.read_bytes(), name
```

## Saves, provenance, and compatibility

Save format remains `fsbot_save: 1`. New files add a top-level `engine`
object with `version` and `source_sha256`; it is alongside `meta`, `log`,
and `state`, not part of the game state. The digest covers engine Python
sources excluding tests, plus supplied reference bytes. It is independent
of installation location and is cached for the running process. Restart
after changing code. `load_game()` still returns `(state, meta, log)`.

Git attributes require LF checkouts for Python sources and disable text
conversion for `Reference Documents/**` and archived compatibility JSON.
This keeps byte-level source and fixture identities stable when Git uses
`core.autocrlf=true` on Windows. Preserve that checkout policy; changing a
manifest hash to accommodate converted source would hide a provenance
mismatch rather than repair it.

Older valid version-1 saves without writer identity still load. Different
engine identities are not automatically rejected: a source digest identifies
the writer, while the save-format and board validators govern whether a file
can be read. Successful loading does not promise that different rules-engine
versions will replay every decision identically.

[Compatibility fixtures](fs_bot/tests/fixtures/compatibility_8ef88e2/manifest.json)
were generated using the unmodified `8ef88e2` source, with the original
serializer. They cover a pending card turn, an interrupted Frumentum action
with an accepted response, and a real seed-3 game's pre/post-Interlude
boundaries. They are controlled fixtures, not recovered user saves. Tests
compare continued board/RNG state and, for the assistant case, session
metadata and decision logs against results from that old engine. Ephemeral
diagnostic ordering is outside this historical comparison.

Preserve old fixtures and manifests when adding coverage for a new version.
Record any intentional incompatibility explicitly; do not regenerate old
expected outcomes with new code and call that backward compatibility.

Before treating a revision as a release checkpoint, run the full suite,
relevant scenario/edition checks, and the clean-install smoke. Record the
source revision, artifact hashes, results, and any compatibility limits.
Update `fs_bot/version.py` and the changelog when preparing a subsequent
version. See [the self-play workflow](SELFPLAY_PLAYBOOK.md) for game-validation
commands and evidence requirements.
