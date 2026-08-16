from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SupplyChainTests(unittest.TestCase):
    def test_runtime_dependencies_are_exactly_pinned(self):
        requirements = [
            line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]

        self.assertTrue(requirements)
        self.assertTrue(all("==" in requirement for requirement in requirements))
        self.assertTrue(all(">=" not in requirement for requirement in requirements))

    def test_python_image_is_versioned_and_digest_pinned(self):
        first_line = (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()[0]

        self.assertTrue(first_line.startswith("FROM python:3.12.13-slim-bookworm@sha256:"))


if __name__ == "__main__":
    unittest.main()
