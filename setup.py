"""Copy the unchanged reference inputs into a local distribution at build time.

The checkout keeps one authoritative copy in Reference Documents. Wheels
need those same bytes for card display and the rules-citation utility.
"""
from pathlib import Path
from shutil import copy2

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        source = Path(__file__).resolve().parent / "Reference Documents"
        if not (source / "Card Reference").is_file():
            raise FileNotFoundError("The build requires the supplied Reference Documents")
        destination = Path(self.build_lib) / "fs_bot" / "_references"
        for path in sorted(source.rglob("*")):
            if path.is_file():
                target = destination / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                copy2(path, target)


setup(cmdclass={"build_py": BuildPy})
