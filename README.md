# Week 3 Assignment: Refactoring the Legacy Monolith

## Structure

- `original/legacy_enrollment_processor.py` — the inherited God Object script (317 lines), plus the sample `students.csv` it was tested against.
- `tests/` — the Phase 1/Phase 2 characterization + unit test suite (pytest). See below.
- `refactored/` — the Clean Architecture rewrite:
  - `domain/` — business rules (course catalog, prerequisite checks, credit limits). No I/O.
  - `infrastructure/` — CSV reading, SQLite persistence, simulated email.
  - `presentation/` — HTML report generation.
  - `main.py` — orchestrator that wires the layers together. Run with:
    ```
    cd refactored
    PYTHONPATH=. python3 main.py
    ```
  - `ARCHITECTURE.md` — the Step 1 code-smell analysis, Step 2 layering blueprint, and an explanation of the test-driven safety net (Section 4).
  - `PROMPTS.txt` — the exact prompts used to guide the AI assistant through Phase 1 (locking behavior) and Steps 1–4 (mapping, blueprint, extraction, orchestration).

## Golden Rule: "No tests. No refactoring."

Following the lecture's required workflow, a pytest characterization suite was
generated and run against the **original, unmodified** legacy script first,
locking in its exact behavior (including quirks like silently dropping rows
with a blank `student_id`). Only after that suite passed 100% did the
extraction into `domain/`, `infrastructure/`, and `presentation/` begin. The
same golden expectations (`tests/golden_results.py`) are then re-run against
`refactored/main.py` with zero changes to the expected values — proving the
refactor is behavior-preserving rather than just "probably fine."

Run everything with:
```
pip install -r requirements.txt
python3 -m pytest tests/ -v
```
35 tests, all passing, against both the legacy script and the refactored package.

## Verification

Both `original/legacy_enrollment_processor.py` and `refactored/main.py` were run against the same `students.csv`. The resulting `enrollment.db` rows (student_id, course_code, status, reason) and `report.html` output (excluding the generated timestamp) are byte-for-byte identical between the two versions — confirmed both manually and by the automated `tests/test_*_characterization.py` suites.
