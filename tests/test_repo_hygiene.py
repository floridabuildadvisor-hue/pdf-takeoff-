"""Repository hygiene checks: dependencies, ignore rules and CI coverage.

These tests read the repo's own config files. They keep the install, the CI
trigger paths and the "no client files in git" rules from drifting silently.
"""

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_PATH_FILTERS = (
    '"**.py"',
    '"tests/**"',
    '"requirements.txt"',
    '".claude/**"',
    '"docs/**"',
)


def _requirement_lines():
    text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    return [
        line.strip() for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


class RequirementsTests(unittest.TestCase):
    def test_pillow_is_listed_because_page_rendering_needs_it(self):
        names = [line.split("==")[0].lower() for line in _requirement_lines()]
        self.assertIn("pillow", names)

    def test_every_requirement_is_pinned_to_an_exact_version(self):
        for line in _requirement_lines():
            self.assertRegex(line, r"^[A-Za-z0-9_.-]+==\d[\w.]*$")


class GitignoreTests(unittest.TestCase):
    def test_generated_reports_and_plan_pdfs_are_ignored(self):
        lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("output/", lines)
        self.assertIn("*.pdf", lines)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = (
            REPO_ROOT / ".github" / "workflows" / "validate.yml"
        ).read_text(encoding="utf-8")

    def test_ci_installs_requirements_before_running_tests(self):
        install = self.workflow.find("pip install -r requirements.txt")
        run_tests = self.workflow.find("unittest discover")
        self.assertNotEqual(install, -1)
        self.assertLess(install, run_tests)

    def test_ci_path_filters_cover_code_tests_requirements_and_docs(self):
        for path_filter in CI_PATH_FILTERS:
            # Once under push and once under pull_request.
            self.assertEqual(self.workflow.count(path_filter), 2, path_filter)


class GitIndexTests(unittest.TestCase):
    def test_index_has_no_gitlink_entries(self):
        try:
            result = subprocess.run(
                ["git", "ls-files", "--stage"],
                cwd=REPO_ROOT, capture_output=True, text=True, check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not running inside a git checkout")
        gitlinks = [
            line for line in result.stdout.splitlines() if line.startswith("160000 ")
        ]
        self.assertEqual(gitlinks, [])


if __name__ == "__main__":
    unittest.main()
