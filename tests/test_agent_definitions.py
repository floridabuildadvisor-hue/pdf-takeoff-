"""Checks on the subagent files in .claude/agents/ and their rulebook.

These tests only read the Markdown files. They do not run any agent, so they
say nothing about how an agent behaves on a plan set.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".claude" / "agents"
RULEBOOK = ROOT / "docs" / "agent-system.md"
SKILL = ROOT / ".claude" / "skills" / "pdf-drawing-intelligence" / "SKILL.md"

ORCHESTRATOR = "project-orchestrator"
PROJECT_AGENTS = {
    ORCHESTRATOR,
    "pdf-drawing-specialist",
    "architectural-plan-reviewer",
    "structural-plan-reviewer",
    "mep-civil-reviewer",
    "quantity-takeoff-agent",
    "cost-estimator",
    "senior-estimator-reviewer",
    "qa-compliance-reviewer",
    "report-proposal-specialist",
}
CODE_AGENTS = {"architect-reviewer", "qa-test-runner", "takeoff-domain-reviewer"}
READ_ONLY_AGENTS = {
    ORCHESTRATOR,
    "senior-estimator-reviewer",
    "qa-compliance-reviewer",
    "architect-reviewer",
    "takeoff-domain-reviewer",
}
PROJECT_FILE_WRITERS = {
    "architectural-plan-reviewer",
    "structural-plan-reviewer",
    "mep-civil-reviewer",
    "quantity-takeoff-agent",
    "cost-estimator",
    "report-proposal-specialist",
}
RECORD_PREFIXES = {
    "pdf-drawing-specialist": "DOC-",
    "architectural-plan-reviewer": "ARC-",
    "structural-plan-reviewer": "STR-",
    "mep-civil-reviewer": "MEP-",
    "quantity-takeoff-agent": "QTO-",
    "cost-estimator": "EST-",
    "senior-estimator-reviewer": "L2-",
    "qa-compliance-reviewer": "L3-",
    "report-proposal-specialist": "RPT-",
}
RECORD_FIELDS = (
    "id", "based_on", "file", "page", "sheet", "revision", "as_printed", "bbox",
    "method", "status",
)
EVIDENCE_FILES = ("commands.txt", "SHA256SUMS", "CHECK.md")
HASH_CHECK = "shasum -a 256 -c 02_Working/{folder}/SHA256SUMS"
PACKAGE_CHECK = "python3 -B evidence_package.py"
TEST_COMMAND = "python3 -m unittest discover -s tests"
BOQ_COMMAND = "python3 -B takeoff_records.py"
TAKEOFF_COLUMNS = (
    "record_type", "item", "description", "dimension", "formula", "quantity", "unit",
    "assumptions",
)
GATE_VALUES = "<pass|fail|not started>"
KNOWN_TOOLS = {"Agent", "Read", "Grep", "Glob", "Bash", "Write", "Edit"}
PLAN_FIELDS = ("scope", "assumptions", "risks", "acceptance criteria")
BANNED_WORDING = (
    "meets code",
    "structurally adequate",
    "certified",
    "engineered",
    "complies",
)
PROHIBITION = re.compile(r"\b(never|no|not|flag)\b", re.IGNORECASE)
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
AGENT_ALLOWLIST = re.compile(r"Agent\(([^)]*)\)")
MARKDOWN_LINK = re.compile(r"\]\(([^)#]+\.md)\)")
LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def load_agent(path: Path) -> tuple[dict[str, str], str]:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(f"{path.name} does not start with YAML frontmatter")
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value.strip()
    return fields, match.group(2)


def tool_names(tools: str) -> list[str]:
    return [name.strip() for name in AGENT_ALLOWLIST.sub("Agent", tools).split(",")]


def one_line(text: str) -> str:
    return " ".join(text.split())


def text_blocks(text: str) -> list[str]:
    """Split Markdown into paragraphs and list items."""
    blocks, current = [], []
    for line in text.splitlines():
        if not line.strip() or LIST_ITEM.match(line):
            if current:
                blocks.append(" ".join(current))
            current = []
        if line.strip():
            current.append(line.strip())
    if current:
        blocks.append(" ".join(current))
    return blocks


class AgentFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agents = {
            path.stem: load_agent(path) for path in sorted(AGENTS_DIR.glob("*.md"))
        }

    def test_the_expected_thirteen_agents_exist(self):
        self.assertEqual(set(self.agents), PROJECT_AGENTS | CODE_AGENTS)

    def test_frontmatter_has_name_description_and_tools(self):
        for stem, (fields, _) in self.agents.items():
            with self.subTest(agent=stem):
                self.assertEqual(set(fields), {"name", "description", "tools"})
                self.assertEqual(fields["name"], stem)

    def test_description_says_when_to_use_the_agent(self):
        for stem, (fields, _) in self.agents.items():
            with self.subTest(agent=stem):
                self.assertIn("Use ", fields["description"])
                self.assertLessEqual(len(fields["description"]), 1024)

    def test_tools_are_known_tool_names(self):
        for stem, (fields, _) in self.agents.items():
            with self.subTest(agent=stem):
                self.assertLessEqual(set(tool_names(fields["tools"])), KNOWN_TOOLS)

    def test_read_only_agents_cannot_write_files(self):
        for stem in READ_ONLY_AGENTS:
            with self.subTest(agent=stem):
                tools = set(tool_names(self.agents[stem][0]["tools"]))
                self.assertFalse(tools & {"Write", "Edit"})

    def test_only_the_orchestrator_can_start_other_agents(self):
        for stem, (fields, _) in self.agents.items():
            with self.subTest(agent=stem):
                has_agent_tool = "Agent" in tool_names(fields["tools"])
                self.assertEqual(has_agent_tool, stem == ORCHESTRATOR)

    def test_orchestrator_can_delegate_to_every_other_agent(self):
        match = AGENT_ALLOWLIST.search(self.agents[ORCHESTRATOR][0]["tools"])
        self.assertIsNotNone(match)
        allowed = {name.strip() for name in match.group(1).split(",")}
        self.assertEqual(allowed, set(self.agents) - {ORCHESTRATOR})

    def test_every_agent_reads_the_rulebook(self):
        for stem, (_, body) in self.agents.items():
            with self.subTest(agent=stem):
                self.assertIn("docs/agent-system.md", body)

    def test_every_specialist_returns_a_plan_first(self):
        for stem, (_, body) in self.agents.items():
            if stem == ORCHESTRATOR:
                continue
            with self.subTest(agent=stem):
                self.assertIn("## Plan first", body)
                section = body.split("## Plan first", 1)[1].split("\n## ", 1)[0].lower()
                for field in PLAN_FIELDS:
                    self.assertIn(field, one_line(section))
                self.assertRegex(section, r"files|sheets")

    def test_orchestrator_plan_names_the_five_fields(self):
        body = one_line(self.agents[ORCHESTRATOR][1]).lower()
        for field in PLAN_FIELDS + ("files affected",):
            self.assertIn(field, body)

    def test_orchestrator_ends_with_the_decision_report(self):
        body = self.agents[ORCHESTRATOR][1]
        for field in ("Decision needed:", "Recommendation:", "Gates:", "If you say yes:"):
            self.assertIn(field, body)

    def test_agents_with_a_shell_are_told_never_to_commit(self):
        for stem, (fields, body) in self.agents.items():
            if "Bash" not in tool_names(fields["tools"]):
                continue
            with self.subTest(agent=stem):
                self.assertRegex(body, r"[Nn]ever\s+commit")

    def test_project_writers_keep_client_data_out_of_the_repo(self):
        for stem in PROJECT_FILE_WRITERS:
            with self.subTest(agent=stem):
                self.assertIn(
                    "Never write client data in this repo", self.agents[stem][1]
                )

    def return_section(self, stem: str) -> str:
        """The section that says what the agent hands back."""
        body = self.agents[stem][1]
        heading = "## 5. Give one decision" if stem == ORCHESTRATOR else "## Return"
        self.assertIn(heading, body)
        return one_line(body.split(heading, 1)[1].split("\n## ", 1)[0])

    def test_every_project_agent_returns_its_evidence(self):
        for stem in PROJECT_AGENTS:
            with self.subTest(agent=stem):
                section = self.return_section(stem)
                self.assertIn("evidence", section.lower())
                self.assertIn("section 9", section)

    def test_each_producer_gives_its_records_their_own_id_prefix(self):
        for stem, prefix in RECORD_PREFIXES.items():
            with self.subTest(agent=stem):
                self.assertIn(f"`{prefix}`", self.agents[stem][1])

    def test_file_writing_project_agents_leave_a_checkable_package(self):
        for stem in PROJECT_AGENTS - READ_ONLY_AGENTS:
            with self.subTest(agent=stem):
                section = self.return_section(stem)
                hash_check = HASH_CHECK.format(folder=stem)
                for item in (*EVIDENCE_FILES, hash_check, "never in a file"):
                    self.assertIn(item, section)

    def test_file_writing_project_agents_keep_scratch_work_in_their_folder(self):
        for stem in PROJECT_AGENTS - READ_ONLY_AGENTS:
            with self.subTest(agent=stem):
                self.assertIn("`scratch/`", self.agents[stem][1])

    def test_read_only_project_agents_write_no_file_anywhere(self):
        for stem in PROJECT_AGENTS & READ_ONLY_AGENTS:
            with self.subTest(agent=stem):
                self.assertIn("not even a temporary one", one_line(self.agents[stem][1]))

    def test_orchestrator_sends_the_estimate_to_level_2(self):
        body = one_line(self.agents[ORCHESTRATOR][1])
        self.assertIn("Level 2 runs again on the estimate", body)

    def test_later_stages_name_the_records_they_build_on(self):
        for stem in set(RECORD_PREFIXES) - {"pdf-drawing-specialist"}:
            with self.subTest(agent=stem):
                self.assertIn("`based_on`", self.agents[stem][1])

    def test_reviewers_show_expected_and_found_values(self):
        for stem in ("senior-estimator-reviewer", "qa-compliance-reviewer"):
            with self.subTest(agent=stem):
                section = self.return_section(stem)
                for column in ("`expected`", "`found`", "`based_on`"):
                    self.assertIn(column, section)

    def test_orchestrator_rechecks_every_package_itself(self):
        body = self.agents[ORCHESTRATOR][1]
        step = one_line(body.split("## 4. Check the results", 1)[1].split("\n## ", 1)[0])
        hash_check = HASH_CHECK.format(folder="<agent>")
        for item in (PACKAGE_CHECK, hash_check, "`diff`", "`based_on`", "02_Working/review/"):
            with self.subTest(item=item):
                self.assertIn(item, step)
        self.assertRegex(one_line(body), r"Why: .*record ID")

    def test_orchestrator_may_run_every_command_its_steps_name(self):
        body = self.agents[ORCHESTRATOR][1]
        self.assertIn(TEST_COMMAND, one_line(body.split("## Rules", 1)[0]))
        rules = one_line(body.split("## Rules", 1)[1])
        commands = (TEST_COMMAND, PACKAGE_CHECK, HASH_CHECK.format(folder="<agent>"))
        for command in commands:
            with self.subTest(command=command):
                self.assertIn(f"`{command}", rules)

    def test_orchestrator_can_report_a_gate_it_has_not_reached(self):
        self.assertEqual(self.agents[ORCHESTRATOR][1].count(GATE_VALUES), 3)

    def test_takeoff_agent_writes_the_columns_the_code_reads(self):
        body = self.agents["quantity-takeoff-agent"][1]
        for column in TAKEOFF_COLUMNS:
            with self.subTest(column=column):
                self.assertIn(f"`{column}`", body)
        self.assertIn(PACKAGE_CHECK, one_line(body))

    def test_report_agent_builds_the_boq_lines_with_the_repo_code(self):
        body = one_line(self.agents["report-proposal-specialist"][1])
        for item in (BOQ_COMMAND, "NOT EXPORTED", "FLAG"):
            with self.subTest(item=item):
                self.assertIn(item, body)

    def test_final_qa_runs_the_package_check(self):
        self.assertIn(PACKAGE_CHECK, one_line(self.agents["qa-compliance-reviewer"][1]))

    def test_engineering_wording_appears_only_as_a_prohibition(self):
        texts = {stem: body for stem, (_, body) in self.agents.items()}
        texts["agent-system.md"] = RULEBOOK.read_text(encoding="utf-8")
        for name, text in texts.items():
            for block in text_blocks(text):
                for phrase in BANNED_WORDING:
                    if phrase in block.lower():
                        with self.subTest(file=name, phrase=phrase):
                            self.assertRegex(block, PROHIBITION)


class RulebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = RULEBOOK.read_text(encoding="utf-8")
        cls.flat = one_line(cls.text)
        cls.agent_names = {path.stem for path in AGENTS_DIR.glob("*.md")}

    def section(self, number: int) -> str:
        start = self.text.index(f"\n## {number}. ")
        end = self.text.find(f"\n## {number + 1}. ", start)
        return self.text[start:] if end == -1 else self.text[start:end]

    def test_has_twelve_numbered_sections(self):
        numbers = re.findall(r"^## (\d+)\. ", self.text, flags=re.MULTILINE)
        self.assertEqual(numbers, [str(n) for n in range(1, 13)])

    def test_organization_lists_every_agent(self):
        for name in self.agent_names:
            with self.subTest(agent=name):
                self.assertIn(f"| `{name}` |", self.section(2))

    def test_names_the_five_stages(self):
        stages = (
            "| 1 | Document intake and project coordination |",
            "| 2 | Construction drawings interpretation |",
            "| 3 | Quantity takeoff |",
            "| 4 | Cost estimating |",
            "| 5 | Review, QA and report |",
        )
        for stage in stages:
            with self.subTest(stage=stage):
                self.assertIn(stage, self.section(3))

    def test_delegation_table_covers_every_specialist(self):
        for name in self.agent_names - {ORCHESTRATOR}:
            with self.subTest(agent=name):
                self.assertIn(f"\n| `{name}` |", self.section(5))

    def test_names_the_four_quality_gates(self):
        for gate in ("1. Implementation", "2. Testing", "3. Review", "4. Release"):
            with self.subTest(gate=gate):
                self.assertIn(f"| **{gate}** |", self.section(6))

    def test_names_the_three_review_levels(self):
        levels = (
            "Production review (Level 1)",
            "Independent technical review (Level 2)",
            "Final QA and authorization (Level 3)",
        )
        for level in levels:
            with self.subTest(level=level):
                self.assertIn(level, self.section(7))

    def test_only_the_owner_authorizes(self):
        self.assertIn("The owner authorizes. No agent does.", self.flat)

    def test_reviewer_checklist_has_the_eleven_checks(self):
        checks = (
            "Drawing scale", "Sheet reference", "Measurements", "Units",
            "Duplicates", "Missing scope", "Openings", "Assemblies", "Waste",
            "Pricing", "Assumptions",
        )
        for number, check in enumerate(checks, start=1):
            with self.subTest(check=check):
                self.assertIn(f"| {number} | **{check}** |", self.section(8))

    def test_decision_report_has_its_fields(self):
        for field in ("Decision needed:", "Recommendation:", "Gates:", "If you say yes:"):
            with self.subTest(field=field):
                self.assertIn(field, self.section(11))

    def test_records_section_defines_the_evidence_package(self):
        section = one_line(self.section(9))
        hash_check = HASH_CHECK.format(folder="<agent>")
        for item in (*EVIDENCE_FILES, hash_check, "/Rotate", "bottom left", "get_charbox",
                     "`02_Working/<agent>/`", "`records.csv`", "`register.csv`",
                     PACKAGE_CHECK):
            with self.subTest(item=item):
                self.assertIn(item, section)
        for field in RECORD_FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", section)
        for stem, prefix in RECORD_PREFIXES.items():
            with self.subTest(agent=stem):
                self.assertIn(f"| `{stem}` | `{prefix}` |", section)

    def test_records_section_gives_one_form_for_each_special_case(self):
        section = one_line(self.section(9))
        cases = (
            "never in a file", "One row cites one page", "`see based_on`", "`drawn`",
            "get_bounds", "`line <n>`", "`scratch/`", "not even a temporary one",
        )
        for item in cases:
            with self.subTest(item=item):
                self.assertIn(item, section)

    def test_records_section_defines_the_takeoff_columns(self):
        section = one_line(self.section(9))
        for column in TAKEOFF_COLUMNS:
            with self.subTest(column=column):
                self.assertIn(f"`{column}`", section)
        for item in (BOQ_COMMAND, "`quantity`", "never gets a value"):
            with self.subTest(item=item):
                self.assertIn(item, section)

    def test_documented_columns_match_the_code(self):
        import evidence_package
        import takeoff_records
        self.assertEqual(evidence_package.REQUIRED_COLUMNS, RECORD_FIELDS)
        self.assertEqual(takeoff_records.TAKEOFF_COLUMNS, TAKEOFF_COLUMNS)
        writers = {k: v for k, v in RECORD_PREFIXES.items() if k not in READ_ONLY_AGENTS}
        self.assertEqual(evidence_package.ID_PREFIXES, writers)

    def test_decision_report_can_show_a_gate_not_reached(self):
        self.assertEqual(self.section(11).count(GATE_VALUES), 3)

    def test_level_2_also_reviews_the_estimate(self):
        self.assertIn("Level 2 runs again on the estimate", one_line(self.section(7)))

    def test_gates_and_rules_require_evidence(self):
        gates = one_line(self.section(6))
        self.assertIn(PACKAGE_CHECK, gates)
        self.assertIn(HASH_CHECK.format(folder="<agent>"), gates)
        self.assertIn("**Evidence, not summaries.**", self.section(12))


class LinkTests(unittest.TestCase):
    def test_skill_links_every_agent_and_the_rulebook(self):
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("../../../docs/agent-system.md", skill)
        for path in AGENTS_DIR.glob("*.md"):
            with self.subTest(agent=path.stem):
                self.assertIn(f"../../agents/{path.name}", skill)

    def test_relative_markdown_links_resolve(self):
        for path in [SKILL, RULEBOOK, *AGENTS_DIR.glob("*.md")]:
            for link in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
                with self.subTest(file=path.name, link=link):
                    self.assertTrue((path.parent / link).resolve().exists())


if __name__ == "__main__":
    unittest.main()
