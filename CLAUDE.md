# pdf-takeoff-

Python command-line tools that read construction plan PDFs and produce review material for
a quantity takeoff. Read the project skill before any work here:
[.claude/skills/pdf-drawing-intelligence/SKILL.md](.claude/skills/pdf-drawing-intelligence/SKILL.md).
The takeoff method is in [TAKEOFF_METHOD.md](TAKEOFF_METHOD.md). If the code and the docs
disagree, the code wins; report the difference.

## Commands

Use `python3` (`python` is not on PATH locally).

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
python3 pdf_intelligence.py path/to/plans.pdf
python3 visual_inspect.py path/to/plans.pdf
```

## Rules

- **Extraction and organisation only.** The tools count and measure what is drawn. No
  design, calculations, opinions, inspections or seals.
- **Estimator language only**, in code, reports, docs and commit messages: "extracted",
  "measured", "flagged for review", "as printed on sheet X". Never "meets code",
  "certified", "approved", "engineered" or "structural/mechanical audit".
- **No client data.** This repository is public. Never commit client PDFs, names,
  addresses or generated reports. `output/` and `*.pdf` are git-ignored. Fixtures are
  synthetic or plain strings.
- **Test first.** Commit the failing test as `test:` before its `feat:` or `fix:` commit.
  Never delete, skip or weaken a test.
- US Customary units. Never invent a missing dimension or scale; report it as unknown.
