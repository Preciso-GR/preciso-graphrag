"""Reject development files and missing modules in a release wheel or source archive."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def check_distribution(directory: Path):
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected exactly one wheel and one source archive")
    expected = {p.relative_to("src").as_posix() for p in Path("src").rglob("*.py")}
    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_names = {n for n in archive.namelist() if not n.endswith("/")}
    modules = {n for n in wheel_names if ".dist-info/" not in n}
    if modules != expected:
        raise ValueError(f"Wheel module mismatch: missing={expected - modules}, extra={modules - expected}")
    with tarfile.open(sources[0], "r:gz") as archive:
        members = archive.getmembers()
    if any(m.issym() or m.islnk() for m in members):
        raise ValueError("Source archive must not contain links")
    source_names = {str(PurePosixPath(m.name).relative_to(PurePosixPath(m.name).parts[0]))
                    for m in members if m.isfile()}
    roots = {"README.md", "LICENSE", "pyproject.toml", "requirements.txt",
             "MANIFEST.in", "PKG-INFO", "setup.cfg"}
    for name in source_names:
        if name in roots or name.removeprefix("src/") in expected and name.startswith("src/"):
            continue
        # setuptools writes metadata needed to build the wheel from the sdist.
        if name.startswith("src/preciso_graphrag.egg-info/") and name.endswith(".txt"):
            continue
        if name == "src/preciso_graphrag.egg-info/PKG-INFO":
            continue
        raise ValueError(f"Unexpected source archive file: {name}")
    required = {"src/" + name for name in expected} | {"pyproject.toml", "requirements.txt", "README.md", "LICENSE"}
    if not required <= source_names:
        raise ValueError(f"Source archive missing: {required - source_names}")
    print(f"Verified {len(expected)} Python modules; no docs, tests, examples, models, or local data in distributions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path("dist"))
    check_distribution(parser.parse_args().directory)
