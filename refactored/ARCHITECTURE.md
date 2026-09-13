# ARCHITECTURE.md
### Analysis of `legacy_enrollment_processor.py`
*(Generated in the role of Senior Systems Architect, as part of Step 1 of the refactor.)*

## 1. What the script does, end to end

`legacy_enrollment_processor.py` is a single 317-line file. Running `main()` executes the following linear sequence, with no layer boundaries between steps:

1. **Wipe and recreate the database.** `main()` deletes `enrollment.db` if it exists, opens a new SQLite connection (`get_connection`), and calls `setup_database()`, which drops and recreates the `enrollments` table using raw SQL embedded in a function.
2. **Read and clean the CSV.** `read_requests()` opens `students.csv`, normalizes inconsistent headers (mixed case, stray whitespace), and hand-cleans every field: trims strings, lowercases emails, uppercases course codes, parses GPA as a float with a bare `try/except`, splits a pipe-delimited `completed_courses` string into a list, and interprets several string variants (`"y"`, `"yes"`, `"true"`, `"1"`) as a boolean override flag. Rows with no `student_id` are silently dropped.
3. **Evaluate business rules per row, inline.** For each parsed request, `process_enrollment()`:
   - Looks up the course in the hard-coded `COURSE_CATALOG` dict declared at module scope.
   - Checks prerequisites via `check_prerequisites()`, allowing a bypass if `override` is set.
   - Computes a GPA-based credit limit (`get_credit_limit()`) — 18 credits normally, 21 for GPA ≥ 3.5.
   - Mutates the **module-level global** `running_credit_totals` dict to accumulate each student's credit load across rows in the same run, and rejects the request if the new total would exceed the limit.
4. **Write to the database inline.** Whatever the outcome, `_record_result()` immediately runs an `INSERT` and commits, from inside the same function that just did business-rule evaluation.
5. **"Send" an email inline.** `_queue_email()` builds a subject/body string, appends it to the module-level global `email_log` list, and prints a line to stdout — all still inside the same call stack as steps 3–4.
6. **Build an HTML report.** After every row has been processed, `generate_html_report()` string-concatenates raw HTML (including inline CSS) row by row using `.format()`, then writes it to `report.html`.
7. **Print a summary** of counts and exit.

Every one of these concerns — database schema, file parsing, business policy, persistence, notification, and HTML rendering — lives in the same file, and several live in the *same function* (`process_enrollment`).

## 2. Code smells identified

### a) God Object / God Function
`legacy_enrollment_processor.py` as a whole is a God Object: one file owns database schema, data parsing, business policy, persistence, notification, and rendering. Within it, `process_enrollment()` is a God Function specifically — it single-handedly does prerequisite checking, credit-limit math, global state mutation, a database write, *and* triggers an email, all in ~35 lines. There is no way to test "does this request pass the business rules?" without also touching SQLite and stdout.

### b) Inappropriate / Global Mutable State
`running_credit_totals` and `email_log` are module-level globals mutated from inside `process_enrollment()` and `_queue_email()` via the `global` keyword. This makes the functions impure and order-dependent: calling `process_enrollment()` twice for the same student produces different results depending on prior calls, but nothing in the function signature reveals that. It also makes the script impossible to run twice in the same process (e.g., in a test suite) without manually resetting hidden state.

### c) Rigidity / Shotgun Surgery (the smell the assignment explicitly calls out)
Because business rules, persistence, and presentation are interleaved, a small change in one concern forces edits scattered across the file. For example: changing how failures are reported (say, to skip DB writes for a certain failure type) requires touching `process_enrollment`, `_record_result`, `_queue_email`, and possibly `generate_html_report` — four places for one behavioral change. Similarly, swapping SQLite for Postgres, or plain-text email for a real provider, both require editing the same function that also contains the prerequisite/credit-limit logic, risking an unrelated business-rule bug.

### d) Fragility (the "immobility" the assignment calls out)
None of the logic can be reused or moved independently. The business rules (`check_prerequisites`, `get_credit_limit`) are free functions, but they're only ever called from inside `process_enrollment`, which is itself welded to a live `sqlite3.Connection` argument. You cannot import "just the credit-limit rule" into another script or a unit test without dragging in `sqlite3`, file paths, and the global dictionaries — a classic sign of Immobility.

### e) Primitive/String Obsession in Presentation
`generate_html_report()` builds markup via nested `.format()` calls on raw strings, mixing structure (table rows), styling (inline `<style>` block), and content in one block. There's no separation between "what data goes in the report" and "how HTML represents that data," so any layout change risks breaking the string interpolation.

### f) No Dependency Injection / Hidden Dependencies
Functions reach out to module-level constants (`DB_PATH`, `CSV_PATH`, `REPORT_PATH`, `COURSE_CATALOG`) directly rather than receiving them as parameters. This makes it impossible to point the script at a different catalog, database, or file path without editing the source, and impossible to substitute a fake/in-memory version for testing.

## 3. Proposed layered structure (Step 2 blueprint)

To eliminate the smells above, the logic is separated into three layers with a one-directional dependency rule: **Presentation and Infrastructure may depend on Domain; Domain depends on nothing.**

```
refactored/
├── domain/
│   ├── models.py            # EnrollmentRequest, Course, EnrollmentDecision (plain dataclasses)
│   ├── catalog.py           # CourseCatalog - business reference data
│   └── enrollment_rules.py  # EnrollmentPolicy, CreditLedger - prerequisite & credit-limit rules
├── infrastructure/
│   ├── csv_reader.py        # EnrollmentCsvReader - messy CSV parsing -> domain objects
│   ├── db_manager.py        # EnrollmentDatabase - SQLite schema + inserts
│   └── email_service.py     # EmailNotifier - simulated notification delivery
├── presentation/
│   └── report_generator.py  # HtmlReportGenerator - renders results as HTML
└── main.py                  # Orchestrator: wires the above together, contains zero business rules
```

## 4. Locking the behavior before touching anything (Golden Rule)

Per the lecture's non-negotiable rule — "No tests. No refactoring." — no
structural change was made until a characterization test suite passed
100% against the original, unmodified script. That suite lives in
`tests/` at the repo root:

- `tests/golden_results.py` — the single source of truth: the exact
  `(student_id, course_code, status, reason)` tuples the legacy script
  produced against `students.csv`, including its quirks (e.g., a row
  with a blank `student_id` is silently dropped — that is preserved,
  not "fixed").
- `tests/test_legacy_characterization.py` — runs the **original**
  `legacy_enrollment_processor.py` as a subprocess and asserts its
  database rows and report totals match `golden_results.py` exactly.
- `tests/test_refactored_characterization.py` — runs **`refactored/main.py`**
  against the *same* golden data. A pass here, with zero changes to the
  expected values, is the actual proof (not just a manual diff) that the
  refactor preserved behavior bug-for-bug.
- `tests/test_domain_rules.py` and `tests/test_csv_reader.py` — unit
  tests on the newly isolated `domain` and `infrastructure` modules,
  including GPA boundary cases (3.49 / 3.5 / 3.51) and override-flag
  string variants — tests that were impossible to write against the
  original because the logic was welded to `sqlite3` and module-level
  globals.

Run the whole suite with:
```
pip install -r requirements.txt
python3 -m pytest tests/ -v
```
All 35 tests pass against both the original script and the refactored
package.

**Why this split resolves each smell:**
- **God Object → gone.** Each file has one reason to change: a new business rule touches only `domain/`; a new storage engine touches only `infrastructure/db_manager.py`; a new report layout touches only `presentation/`.
- **Global mutable state → gone.** `CreditLedger` is an explicit, instantiable class passed into `EnrollmentPolicy`, so state is scoped to a single run and can be reset trivially in tests.
- **Rigidity/Shotgun Surgery → reduced.** Swapping SQLite for another database means editing only `db_manager.py`; the domain rules and HTML report are untouched.
- **Fragility/Immobility → reduced.** `domain/enrollment_rules.py` has no imports from `infrastructure` or `presentation`, so it can be imported and unit-tested (or reused in a different app) in isolation.
- **Hidden dependencies → gone.** `main.py` explicitly constructs and injects the catalog, ledger, reader, database, notifier, and reporter, so every dependency is visible at the call site.
