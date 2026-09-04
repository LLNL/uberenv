#!/usr/bin/env python3

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uberenv


class HostConfigTests(unittest.TestCase):
    def make_env(self, source_dir, destination, pattern="*-host.cmake"):
        spack_env = uberenv.SpackEnv.__new__(uberenv.SpackEnv)
        spack_env.pkg_src_dir = str(source_dir)
        spack_env.dest_dir = str(destination)
        spack_env.pkg_host_config_pattern = pattern
        return spack_env

    def test_source_root_is_preferred_and_all_matches_are_copied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            destination = root / "prefix"
            legacy_dir = source_dir / "spack-build"
            source_dir.mkdir()
            destination.mkdir()
            legacy_dir.mkdir()

            (source_dir / "a-host.cmake").write_text("a", encoding="utf-8")
            (source_dir / "b-host.cmake").write_text("b", encoding="utf-8")
            (source_dir / "unrelated.cmake").write_text("unrelated", encoding="utf-8")
            (legacy_dir / "legacy-host.cmake").write_text("legacy", encoding="utf-8")

            result = self.make_env(source_dir, destination).copy_dev_build_host_configs()

            self.assertEqual(result, 0)
            self.assertEqual((destination / "a-host.cmake").read_text(encoding="utf-8"), "a")
            self.assertEqual((destination / "b-host.cmake").read_text(encoding="utf-8"), "b")
            self.assertFalse((destination / "unrelated.cmake").exists())
            self.assertFalse((destination / "legacy-host.cmake").exists())
            self.assertTrue(legacy_dir.exists())

    def test_legacy_build_directory_is_fallback_and_is_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            destination = root / "prefix"
            legacy_dir = source_dir / "spack-build"
            source_dir.mkdir()
            destination.mkdir()
            legacy_dir.mkdir()

            (legacy_dir / "a-host.cmake").write_text("a", encoding="utf-8")
            (legacy_dir / "b-host.cmake").write_text("b", encoding="utf-8")

            result = self.make_env(source_dir, destination).copy_dev_build_host_configs()

            self.assertEqual(result, 0)
            self.assertEqual((destination / "a-host.cmake").read_text(encoding="utf-8"), "a")
            self.assertEqual((destination / "b-host.cmake").read_text(encoding="utf-8"), "b")
            self.assertFalse(legacy_dir.exists())

    def test_no_match_fails_and_reports_searched_locations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            destination = root / "prefix"
            source_dir.mkdir()
            destination.mkdir()

            spack_env = self.make_env(source_dir, destination, "machine-*.cmake")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = spack_env.copy_dev_build_host_configs()

            self.assertEqual(result, -1)
            self.assertIn("machine-*.cmake", output.getvalue())
            self.assertIn(str(source_dir / "machine-*.cmake"), output.getvalue())
            self.assertIn(
                str(source_dir / "spack-build" / "machine-*.cmake"),
                output.getvalue(),
            )


if __name__ == "__main__":
    unittest.main()
