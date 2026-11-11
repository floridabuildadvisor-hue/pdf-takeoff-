# Takeoff Method

This document defines the operating method for the takeoff workflow used in this repository. The goal is not automation by guesswork; it is a repeatable, auditable process that lets a human check every quantity before it is accepted.

## 1. Source of truth

Every quantity in the BOQ must be traceable to a source.

For each item, record:
- drawing sheet number
- page or detail reference
- dimension or note used
- formula applied
- unit conversion used
- the reviewer or analyst initials

The rule is simple: if you cannot trace the number back to a drawing, it is not a valid takeoff item.

## 2. Auditable BOQ format

Each line in the BOQ should show:
- item code or label
- quantity
- units
- formula
- source sheet
- notes or assumptions

Example structure:

- Item: wall framing
- Quantity: 128.4 LF
- Formula: wall length × stud spacing / 16" adjustment
- Source: Sheet A-102, north wall
- Notes: door opening deducted per detail D-4

This makes the result reviewable by another person without needing the analyst to explain the whole method from memory.

## 3. Clickable markup on the plans

Every countable item should be marked visually on the plan, using an overlay or HTML layer that ties the object to its measurement and sheet.

The intent is to keep the process transparent:
- click the marked item on the plan
- see the quantity or dimension attached to it
- confirm the formula and source drawing
- verify the item against the legend or plan notes

This is a human check step. It is not a substitute for a final review.

## 4. Visual verification rules

Before a takeoff quantity is accepted:
- confirm the item exists on the correct sheet
- confirm the described dimension matches the drawing scale
- confirm the legend or notes are consistent with the symbol or line type
- confirm the quantity is not double-counted
- confirm there are no hidden assumptions not written down

If any of these checks fail, the quantity is flagged for review instead of released.

## 5. Dimension verification

Use written dimensions as the primary comparison against model outputs or computed values.

When there is a mismatch:
- identify the dimension source
- check the phase or revision of the drawing
- check if the item is partial length, reused length, or an opening allowance
- document the adjustment before finalizing the BOQ

The point is not to trust a single algorithm output without checking it against the drawing language itself.

## 6. Sheet index and drawing log

Maintain a `drawings.md` or equivalent index that lists:
- sheet number
- title or discipline
- revision date
- scale
- relevant details or notes
- items extracted from that sheet

This ensures the takeoff is organized by drawing, not by memory.

## 7. Verification loop

The takeoff process should follow this loop:

1. identify the relevant sheet
2. read the dimensions and notes
3. convert the drawing geometry to real-world units
4. apply the correct formula
5. record formula and assumptions
6. mark the item visually on the drawing
7. compare with written dimensions
8. review the BOQ line item before acceptance

This loop is the core of the method and should be preserved even as the code changes.

## 8. What is not in scope

This repository is not an autonomous estimator that learns from raw plans without oversight.

This workflow intentionally avoids:
- hidden model training on project drawings without approval
- unreviewed quantity counts from an unknown symbol set
- silent rule changes without tests and documentation

## 9. Verified examples and tests

To keep the system honest, use verified sample drawings or synthetic examples that contain known-good answers.

These examples should be used for:
- unit tests on formula logic
- regression checks when formulas change
- QA before a takeoff is released

If a plan cannot be shared publicly, use a synthetic example that matches the same rules and is clearly labeled as non-project data.

## 10. Current working standard

The current standard for this repo is:
- every quantity must be traceable to a drawing and a formula
- every count must be visually checked
- every formula change must be tested
- every output item should be explainable to another reviewer

This standard is intentionally conservative and is the preferred default for production takeoff work.
