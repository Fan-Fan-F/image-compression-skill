import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("image_optimizer", ROOT / "scripts" / "image_optimizer.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


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


if __name__ == "__main__":
    unittest.main()
