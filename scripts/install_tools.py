"""Install pinned, optional offline tooling. Running without --apply only lists the plan."""
import argparse
from dataclasses import dataclass
import hashlib
from io import BytesIO
import os
from pathlib import Path
import shutil
import stat
import sys
from tempfile import TemporaryDirectory
import urllib.error
import urllib.request
import zipfile


@dataclass(frozen=True)
class Tool:
    directory: str
    repo: str
    commit: str
    digest: str
    required: tuple

    @property
    def url(self):
        return f"https://codeload.github.com/{self.repo}/zip/{self.commit}"


COPPER_FILES = (
    "LICENSE", "references/copper-tool.md", "references/netlist-tool.md",
    "scripts/compare_netlists.py", "scripts/check_copper_connectivity.py",
    "scripts/check_manufacturing.py", "scripts/run_copper_benchmarks.py",
    "scripts/requirements-manufacturing.txt", "tests/test_netlists.py",
    "tests/test_copper_connectivity.py", "assets/examples/netlist-expected.json",
    "assets/examples/netlist-actual.json",
)
TOOLS = {
    "eprj3": Tool("eprj3-v1.36.1", "easyeda/easyeda-eprj3-skill",
                  "9d65dee4ad2e5dc0ae1ee3bf3e16ae824f230e13",
                  "9c7d319f9615e025e0d7e47203700470d9999d5661833dbc51864c70d66de652",
                  ("scripts/build.js", "package.json", "LICENSE")),
    "copper": Tool("easyeda-pcb-design-bc3c736", "zsy-smu/easyeda-pcb-design",
                   "bc3c73699624e7aa360ff135eb900d0284d3a8df",
                   "1e84ed8e0cf8ac2367946c96aa9f26eed6ad02da2626242ec66c195d21be9887",
                   COPPER_FILES),
    "api-docs": Tool("api-docs-1.1.85", "easyeda/easyeda-api-skill",
                     "998c0e304afaa813540b7446489982bc5256d37e",
                     "c28d494f6e472b4b3a062c45aaff1f59fb0b5b79d5a0db3f05042fb1601a0deb",
                     ("SKILL.md", "references/_index.md")),
}
MAX_DOWNLOAD = 32 * 1024 * 1024
RESERVED = {"AUX", "NUL", "CON", "PRN"} | {f"{p}{i}" for p in ("LPT", "COM") for i in range(1, 10)}


def load_archive(key, tool, archive_dir):
    cache_name = ("api" if key == "api-docs" else key) + f"-{tool.commit}.zip"
    if archive_dir is None:
        stream = urllib.request.urlopen(tool.url, timeout=30)
    else:
        stream = (archive_dir / cache_name).open("rb")
    with stream:
        data = stream.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD or hashlib.sha256(data).hexdigest() != tool.digest:
        raise ValueError(f"{key}: archive size or SHA-256 mismatch ({cache_name})")
    return data


def unpack(key, tool, data, dest):
    root = tool.repo.split("/")[1] + "-" + tool.commit
    seen = set()
    total = 0
    with zipfile.ZipFile(BytesIO(data)) as archive:
        for item in archive.infolist():
            # ZipInfo can normalize Windows separators or truncate at NUL.
            parts = item.orig_filename.removesuffix("/").split("/")
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (parts[0] != root or mode not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or any(p in ("", ".", "..") or p.endswith((" ", "."))
                           or p.split(".")[0].upper() in RESERVED
                           or any(c in '<>:"|?*\\' or ord(c) < 32 for c in p)
                           for p in parts)):
                raise ValueError(f"Unexpected archive member: {item.filename!r}")
            if item.is_dir():
                continue
            if len(parts) < 2:
                raise ValueError("Unexpected archive layout")
            relative = "/".join(parts[1:])
            if key == "copper" and relative not in COPPER_FILES:
                continue
            if key == "api-docs" and not (relative.endswith(".md") or relative == "LICENSE"):
                continue
            total += item.file_size
            if relative.casefold() in seen or total > 64 * 1024 * 1024:
                raise ValueError("Duplicate member or unpacked size limit exceeded")
            seen.add(relative.casefold())
            target = dest.joinpath(*parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
    if any(not (dest / name).is_file() for name in tool.required):
        raise ValueError(f"{key}: required files missing")


def install(keys, root, archive_dir=None):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".easyeda-design-workbench-install.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError(f"Installer lock exists: {lock}") from None
    try:
        with TemporaryDirectory(prefix=".workbench-stage-", dir=root) as staging:
            stage = Path(staging)
            targets = []
            for key in keys:
                tool = TOOLS[key]
                target = root / tool.directory
                if os.path.lexists(target):
                    if target.is_symlink() or not target.is_dir():
                        raise ValueError(f"Destination occupied: {target}")
                    print(f"SKIP existing directory (unverified): {target}")
                    continue
                unpack(key, tool, load_archive(key, tool, archive_dir), stage / tool.directory)
                targets.append(target)
            published = []
            try:
                for target in targets:
                    if os.path.lexists(target):
                        raise ValueError(f"Destination appeared during install: {target}")
                    (stage / target.name).rename(target)
                    published.append(target)
            except (OSError, ValueError):
                for target in reversed(published):
                    target.rename(stage / target.name)
                raise
            for target in published:
                print(f"INSTALLED {target}")
    finally:
        lock.rmdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", nargs="+", choices=list(TOOLS), default=["eprj3", "copper"])
    codex_dir = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    parser.add_argument("--tools-dir", type=Path, default=codex_dir / "easyeda-tools")
    parser.add_argument("--archive-dir", type=Path,
                        help="Offline cache: eprj3-<commit>.zip, copper-<commit>.zip, api-<commit>.zip")
    parser.add_argument("--apply", action="store_true", help="Download and install the listed tools.")
    args = parser.parse_args(argv)
    keys = list(dict.fromkeys(args.tools))
    root = args.tools_dir.expanduser().resolve()
    for key in keys:
        tool = TOOLS[key]
        print(f"{key}  {tool.url}  sha256={tool.digest}\n  -> {root / tool.directory}")
    if not args.apply:
        print("DRY RUN. Use --apply to install.")
        return 0
    try:
        install(keys, root, args.archive_dir)
    except (OSError, ValueError, zipfile.BadZipFile, urllib.error.URLError) as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
