from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install_tools as installer


def fixture(directory, key, extra=None):
    tool = installer.TOOLS[key]
    filename = ("api" if key == "api-docs" else key) + "-" + tool.commit + ".zip"
    archive = directory / filename
    prefix = tool.repo.split("/")[1] + "-" + tool.commit + "/"
    with zipfile.ZipFile(archive, "w") as z:
        for name in tool.required:
            z.writestr(prefix + name, "test fixture")
        z.writestr(prefix + "bridge.run", "not executed")
        if extra:
            name = zipfile.ZipInfo(prefix + extra[0])
            name.filename = prefix + extra[0]
            name.external_attr = extra[1] << 16
            z.writestr(name, "example")
    return replace(tool, digest=hashlib.sha256(archive.read_bytes()).hexdigest())


class ToolInstallerTests(unittest.TestCase):
    def test_dry_run_does_not_fetch_or_create_directory(self):
        with TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            target = Path(temp) / "missing"
            with patch.object(installer, "load_archive", side_effect=AssertionError):
                self.assertEqual(installer.main(["--tools-dir", str(target)]), 0)
            self.assertFalse(target.exists())

    def test_apply_filters_subsets_and_preserves_existing_directory(self):
        with TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            cache = Path(temp)
            root = cache / "installed"
            entries = {k: fixture(cache, k) for k in installer.TOOLS}
            with patch.dict(installer.TOOLS, entries):
                installer.install(list(entries), root, cache)
                copper = root / entries["copper"].directory
                self.assertEqual(len([p for p in copper.rglob("*") if p.is_file()]), len(installer.COPPER_FILES))
                self.assertFalse((root / entries["api-docs"].directory / "bridge.run").exists())
                existing = copper / "LICENSE"
                existing.write_text("user modification")
                with patch.object(installer, "load_archive", side_effect=AssertionError):
                    installer.install(list(entries), root, cache)
                self.assertEqual(existing.read_text(), "user modification")

    def test_failure_in_second_archive_does_not_publish_first_tool(self):
        with TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            cache = Path(temp)
            root = cache / "installed"
            first = fixture(cache, "eprj3")
            fixture(cache, "copper")  # digest intentionally differs from the pinned upstream archive
            with patch.dict(installer.TOOLS, {"eprj3": first}):
                self.assertEqual(installer.main(["--apply", "--archive-dir", str(cache), "--tools-dir", str(root)]), 1)
            self.assertEqual(list(root.iterdir()), [])

    def test_traversal_windows_paths_and_links_rejected(self):
        for name, mode in (("../escaped", 0), ("c:/escaped", 0), ("a\\b", 0),
                           ("AUX.txt", 0), ("link", stat.S_IFLNK | 0o777)):
            with self.subTest(name=name), TemporaryDirectory() as temp:
                cache = Path(temp)
                pin = fixture(cache, "eprj3", (name, mode))
                with patch.dict(installer.TOOLS, {"eprj3": pin}), self.assertRaises(ValueError):
                    installer.install(["eprj3"], cache / "target", cache)
                self.assertEqual(list((cache / "target").iterdir()), [])

    def test_existing_lock_is_preserved(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            lock = root / ".easyeda-design-workbench-install.lock"
            lock.mkdir()
            with self.assertRaises(ValueError):
                installer.install(["copper"], root, root)
            self.assertEqual(list(root.iterdir()), [lock])

    def test_codex_home_default(self):
        with TemporaryDirectory() as temp, patch.dict(installer.os.environ, {"CODEX_HOME": temp}):
            with patch.object(installer, "install") as install, redirect_stdout(io.StringIO()):
                self.assertEqual(installer.main(["--apply", "--tools", "eprj3"]), 0)
                install.assert_called_once_with(["eprj3"], Path(temp).resolve() / "easyeda-tools", None)


if __name__ == "__main__":
    unittest.main()
