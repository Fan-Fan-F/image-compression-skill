import importlib.util
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("image_optimizer", ROOT / "scripts" / "image_optimizer.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MAGICK = os.environ.get("IMAGEMAGICK_BINARY") or shutil.which("magick")
if os.environ.get("REQUIRE_IMAGEMAGICK") == "1" and not MAGICK:
    raise RuntimeError("REQUIRE_IMAGEMAGICK=1 but no ImageMagick binary was configured or found.")


class OptimizerTests(unittest.TestCase):
    def test_supported_inputs(self):
        self.assertIn(".png", MODULE.SUPPORTED_INPUTS)
        self.assertEqual(MODULE.FORMATS["webp"], ".webp")

    def test_webp_command_contains_quality_and_method(self):
        command = MODULE.build_command("magick", Path("in.png"), Path("out.webp"), "webp", 92, None, False)
        self.assertIn("webp:method=6", command)
        self.assertIn("92", command)

    def test_resize_is_aspect_preserving(self):
        command = MODULE.build_command("magick", Path("in.png"), Path("out.webp"), "webp", 90, 2048, False)
        self.assertIn("2048x2048>", command)

    def test_batch_output_preserves_recursive_relative_directory(self):
        source = Path("inputs") / "nested" / "same.png"
        output = Path("optimized") / source.relative_to(Path("inputs")).parent / "same.png"
        self.assertEqual(output, Path("optimized") / "nested" / "same.png")


@unittest.skipUnless(MAGICK, "Real image regressions require existing ImageMagick 7")
class ImageSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.magick = MAGICK

    def image(self, path, color="red", size="48x32", *options):
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.magick, "-size", size, "xc:" + color, *options, str(path)], check=True, capture_output=True)
        return path

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def cli(self, *arguments):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "image_optimizer.py"), *map(str, arguments), "--magick", self.magick], capture_output=True, text=True, timeout=60)
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            payload = None
        return result, payload

    def test_source_is_never_replaced_even_on_failed_size_target(self):
        for impossible in (False, True):
            source = self.image(self.folder / str(impossible) / "source.png", "red", "48x32", "-set", "comment", "original fixture")
            original = self.digest(source)
            arguments = ["optimize", source, "--format", "same", "--output-dir", source.parent, "--strip", "--max-dimension", "8"]
            if impossible:
                arguments += ["--max-mb", "0.000001"]
            result, _ = self.cli(*arguments)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.digest(source), original)

    def test_existing_output_requires_explicit_overwrite(self):
        source = self.image(self.folder / "inputs" / "source.png")
        output = self.image(self.folder / "outputs" / "source.png", "blue", "12x10")
        original = self.digest(output)
        result, _ = self.cli("optimize", source, "--format", "png", "--output-dir", output.parent)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.digest(output), original)

    def test_explicit_overwrite_is_success_only_and_source_safe(self):
        source = self.image(self.folder / "inputs" / "source.png")
        output = self.image(self.folder / "outputs" / "source.png", "blue", "12x10")
        source_hash, old_output = self.digest(source), self.digest(output)
        result, _ = self.cli("optimize", source, "--format", "png", "--output-dir", output.parent, "--max-mb", "0.000001", "--overwrite")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.digest(output), old_output)
        self.assertFalse(any(p.name.startswith(".image-opt-") for p in output.parent.iterdir()))
        result, payload = self.cli("optimize", source, "--format", "png", "--output-dir", output.parent, "--max-dimension", "8", "--overwrite")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.digest(output), old_output)
        self.assertEqual(self.digest(source), source_hash)
        self.assertEqual(payload["results"][0]["output_dimensions"], [8, 5])

    def test_hardlinked_source_is_protected_even_with_overwrite(self):
        source = self.image(self.folder / "inputs" / "source.png")
        output = self.folder / "outputs" / source.name
        output.parent.mkdir()
        os.link(source, output)
        original = self.digest(source)
        result, _ = self.cli("optimize", source, "--output-dir", output.parent, "--max-dimension", "8", "--overwrite")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.digest(source), original)
        self.assertEqual(self.digest(output), original)

    def test_failed_candidate_is_removed_without_publishing(self):
        source = self.image(self.folder / "source.png")
        output = self.folder / "outputs"
        original = self.digest(source)
        result, payload = self.cli("optimize", source, "--output-dir", output, "--max-mb", "0.000001")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.digest(source), original)
        self.assertEqual(payload["results"][0]["status"], "error")
        self.assertEqual(sorted(p.name for p in output.iterdir()), ["manifest.json"])

    def test_encoder_failure_cleans_partial_candidate_and_preserves_existing_output(self):
        source = self.image(self.folder / "inputs" / "source.png")
        output = self.image(self.folder / "outputs" / "source.png", "blue")
        original_source, original_output = self.digest(source), self.digest(output)
        options = SimpleNamespace(format="png", max_mb=None, min_mb=None, quality=None, max_dimension=None, strip=False, mode="compress", overwrite=True)
        original_run = subprocess.run
        def failing_encode(command, **kwargs):
            if command[1] == "identify":
                return original_run(command, **kwargs)
            Path(command[-1]).write_bytes(b"incomplete encoder output")
            raise subprocess.CalledProcessError(1, command)
        with mock.patch.object(MODULE.subprocess, "run", side_effect=failing_encode):
            with self.assertRaises(subprocess.CalledProcessError):
                MODULE.optimize_one(source, output.parent, options, self.magick)
        self.assertEqual(self.digest(source), original_source)
        self.assertEqual(self.digest(output), original_output)
        self.assertEqual(sorted(p.name for p in output.parent.iterdir()), ["source.png"])

    def test_destination_created_while_encoding_is_preserved(self):
        source = self.image(self.folder / "inputs" / "source.png")
        output = self.folder / "outputs" / "source.png"
        options = SimpleNamespace(format="png", max_mb=None, min_mb=None, quality=None, max_dimension=None, strip=False, mode="compress", overwrite=False)
        original_run = subprocess.run
        def encoding_with_racing_writer(command, **kwargs):
            result = original_run(command, **kwargs)
            if command[1] != "identify":
                output.write_bytes(b"concurrent writer")
            return result
        with mock.patch.object(MODULE.subprocess, "run", side_effect=encoding_with_racing_writer):
            with self.assertRaises(FileExistsError):
                MODULE.optimize_one(source, output.parent, options, self.magick)
        self.assertEqual(output.read_bytes(), b"concurrent writer")
        self.assertEqual(sorted(p.name for p in output.parent.iterdir()), ["source.png"])

    def test_manifest_publish_failure_reports_verified_partial_results(self):
        source = self.image(self.folder / "inputs" / "source.png")
        output = self.folder / "outputs"
        result, _ = self.cli("optimize", source, "--output-dir", output, "--max-dimension", "24")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = output / "manifest.json"
        old_manifest, original_source = manifest.read_bytes(), self.digest(source)
        original_replace = os.replace
        def locked_manifest(candidate, destination):
            if Path(destination) == manifest:
                raise PermissionError("simulated report publication lock")
            return original_replace(candidate, destination)
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["image_optimizer.py", "optimize", str(source), "--output-dir", str(output), "--max-dimension", "8", "--overwrite", "--magick", self.magick]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(MODULE.os, "replace", side_effect=locked_manifest), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = MODULE.main()
        self.assertEqual(status, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "partial")
        self.assertIsNone(payload["manifest"])
        self.assertIn("PermissionError", payload["manifest_error"])
        self.assertIn("previous", payload["manifest_error"].lower())
        self.assertEqual(manifest.read_bytes(), old_manifest)
        self.assertEqual(self.digest(source), original_source)
        self.assertEqual(payload["results"][0]["status"], "ok")
        actual = MODULE.identify(self.magick, output / "source.png")
        self.assertEqual(payload["results"][0]["output_dimensions"], [actual["width"], actual["height"]])
        self.assertEqual(payload["results"][0]["output_dimensions"], [8, 5])
        self.assertEqual(payload["results"][0]["output_bytes"], actual["bytes"])
        self.assertEqual(sorted(p.name for p in output.iterdir()), ["manifest.json", "source.png"])

    def test_batch_conversion_collision_outputs_match_manifest(self):
        inputs, output = self.folder / "inputs", self.folder / "outputs"
        sources = [self.image(inputs / "foo.png", "red", "32x20"), self.image(inputs / "foo.jpg", "blue", "24x12"), self.image(inputs / "bar.png", "green", "20x16")]
        hashes = {p: self.digest(p) for p in sources}
        result, payload = self.cli("batch", inputs, "--format", "webp", "--quality", "90", "--output-dir", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        records = payload["results"]
        self.assertEqual({Path(item["output"]).name for item in records}, {"foo.png.webp", "foo.jpg.webp", "bar.webp"})
        self.assertEqual(len({item["output"] for item in records}), 3)
        for item in records:
            info = MODULE.identify(self.magick, Path(item["output"]))
            self.assertEqual(item["output_dimensions"], [info["width"], info["height"]])
            self.assertEqual(item["output_bytes"], info["bytes"])
        self.assertTrue(all(self.digest(p) == hashes[p] for p in sources))

    def test_secondary_filename_collision_is_rejected_before_encoding(self):
        inputs, output = self.folder / "inputs", self.folder / "outputs"
        sources = [self.image(inputs / name) for name in ("foo.jpg", "foo.png", "foo.png.jpg")]
        originals = {p: self.digest(p) for p in sources}
        result, _ = self.cli("batch", inputs, "--format", "webp", "--output-dir", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(self.digest(p) == originals[p] for p in sources))
        self.assertFalse(output.exists())

    def test_recursive_output_subtree_is_excluded_and_relative_paths_preserved(self):
        inputs = self.folder / "inputs"
        output = inputs / "optimized"
        self.image(inputs / "one" / "same.png")
        self.image(inputs / "two" / "same.png", "blue")
        existing = self.image(output / "old.webp", "green")
        original = self.digest(existing)
        result, payload = self.cli("batch", inputs, "--recursive", "--format", "webp", "--output-dir", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual({str(Path(item["output"]).relative_to(output)) for item in payload["results"]}, {str(Path("one/same.webp")), str(Path("two/same.webp"))})
        self.assertEqual(self.digest(existing), original)

    def test_batch_output_equal_input_is_refused(self):
        inputs = self.folder / "inputs"
        source = self.image(inputs / "source.png")
        original = self.digest(source)
        result, _ = self.cli("batch", inputs, "--output-dir", inputs, "--strip", "--max-dimension", "8")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.digest(source), original)

    def test_batch_plan_cannot_target_another_source(self):
        inputs = self.folder / "inputs"
        sources = [self.image(inputs / "same.webp"), self.image(inputs / "inputs" / "same.webp", "blue")]
        originals = {p: self.digest(p) for p in sources}
        result, _ = self.cli("batch", inputs, "--recursive", "--output-dir", self.folder, "--overwrite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("aliases a source", result.stderr)
        self.assertTrue(all(self.digest(p) == originals[p] for p in sources))
        self.assertFalse((self.folder / "same.webp").exists())

    def test_opaque_gray_rgb_and_alpha_are_safe_for_jpeg(self):
        fixtures = [
            ("gray", ["-colorspace", "Gray", "-alpha", "off"], False),
            ("rgb", ["-alpha", "off"], False),
            ("opaque-alpha", ["-alpha", "set", "-define", "png:color-type=6"], True),
        ]
        for name, options, expected_alpha in fixtures:
            source = self.image(self.folder / (name + ".png"), "red", "16x16", *options)
            info = MODULE.identify(self.magick, source)
            self.assertEqual(info["has_alpha"], expected_alpha)
            self.assertTrue(info["is_opaque"])
            result, _ = self.cli("optimize", source, "--format", "jpg", "--quality", "90", "--output-dir", self.folder / name)
            self.assertEqual(result.returncode, 0, result.stderr)
        transparent = self.image(self.folder / "transparent.png", "rgba(255,0,0,0.5)")
        info = MODULE.identify(self.magick, transparent)
        self.assertTrue(info["has_alpha"])
        self.assertFalse(info["is_opaque"])
        result, _ = self.cli("optimize", transparent, "--format", "jpg", "--output-dir", self.folder / "transparent")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.folder / "transparent" / "transparent.jpg").exists())

    def test_multiframe_tiff_is_refused_without_scene_outputs(self):
        source = self.folder / "sequence.tiff"
        subprocess.run([self.magick, "-size", "8x8", "xc:red", "xc:blue", str(source)], check=True, capture_output=True)
        original = self.digest(source)
        output = self.folder / "outputs"
        result, _ = self.cli("optimize", source, "--format", "png", "--output-dir", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.digest(source), original)
        self.assertFalse(list(output.glob("*.png")))

    def test_invalid_numeric_limits_fail_before_creating_output(self):
        source = self.image(self.folder / "source.png")
        for flag, value in [("--max-mb", "nan"), ("--min-mb", "-1"), ("--max-mb", "inf"), ("--quality", "0"), ("--max-dimension", "-2")]:
            output = self.folder / "outputs"
            result, _ = self.cli("optimize", source, flag, value, "--output-dir", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
