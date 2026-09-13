"""
legacy_enrollment_processor.py

Original author: (left the company)
Purpose: reads student course enrollment requests from a CSV, checks
business rules, writes results to a SQLite database, builds an HTML
report, and "sends" email notifications.

WARNING: nobody fully understands this file anymore. Handle with care.
"""

import csv
import sqlite3
import os
from datetime import datetime

DB_PATH = "enrollment.db"
CSV_PATH = "students.csv"
REPORT_PATH = "report.html"

# Hard-coded "course catalog" -- credits and prerequisites live here,
# mixed in with everything else.
COURSE_CATALOG = {
    "CS101": {"credits": 3, "prereqs": []},
    "CS201": {"credits": 3, "prereqs": ["CS101"]},
    "CS301": {"credits": 4, "prereqs": ["CS201"]},
    "MATH110": {"credits": 4, "prereqs": []},
    "MATH210": {"credits": 4, "prereqs": ["MATH110"]},
    "ENG100": {"credits": 3, "prereqs": []},
    "PHYS150": {"credits": 4, "prereqs": ["MATH110"]},
    "PHYS250": {"credits": 4, "prereqs": ["PHYS150", "MATH210"]},
    "HIST101": {"credits": 3, "prereqs": []},
    "ART120": {"credits": 2, "prereqs": []},
}

STANDARD_CREDIT_LIMIT = 18
HONORS_CREDIT_LIMIT = 21
HONORS_GPA_THRESHOLD = 3.5

# global-ish state that gets threaded through everything
running_credit_totals = {}
email_log = []


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn


def setup_database(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS enrollments")
    cur.execute(
        """
        CREATE TABLE enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            student_name TEXT,
            course_code TEXT,
            status TEXT,
            reason TEXT,
            processed_at TEXT
        )
        """
    )
    conn.commit()


def clean_str(value):
    if value is None:
        return ""
    return str(value).strip()


def parse_bool_flag(value):
    v = clean_str(value).lower()
    return v in ("y", "yes", "true", "1")


def read_requests(path):
    """Reads the messy CSV. Headers have inconsistent casing/spacing,
    and some rows have missing fields, so there's a bunch of ad-hoc
    cleanup jammed in here."""
    requests = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # normalize headers because the CSV export tool is inconsistent
        normalized_fieldnames = {
            name: name.strip().lower().replace(" ", "_") for name in reader.fieldnames
        }
        for raw_row in reader:
            row = {normalized_fieldnames[k]: v for k, v in raw_row.items()}

            student_id = clean_str(row.get("student_id"))
            if not student_id:
                # skip totally broken rows
                continue

            name = clean_str(row.get("name")) or "Unknown Student"
            email = clean_str(row.get("email")).lower()
            course_code = clean_str(row.get("course_code")).upper()

            gpa_raw = clean_str(row.get("gpa"))
            try:
                gpa = float(gpa_raw) if gpa_raw else 0.0
            except ValueError:
                gpa = 0.0

            completed_raw = clean_str(row.get("completed_courses"))
            completed_courses = (
                [c.strip().upper() for c in completed_raw.split("|") if c.strip()]
                if completed_raw
                else []
            )

            override = parse_bool_flag(row.get("override_prereq"))

            requests.append(
                {
                    "student_id": student_id,
                    "name": name,
                    "email": email,
                    "gpa": gpa,
                    "completed_courses": completed_courses,
                    "course_code": course_code,
                    "override": override,
                }
            )
    return requests


def check_prerequisites(course_code, completed_courses, override):
    course = COURSE_CATALOG.get(course_code)
    if course is None:
        return False, "Unknown course code"

    missing = [p for p in course["prereqs"] if p not in completed_courses]
    if missing and not override:
        return False, "Missing prerequisites: " + ", ".join(missing)
    if missing and override:
        return True, "Prerequisite override applied for: " + ", ".join(missing)
    return True, ""


def get_credit_limit(gpa):
    if gpa >= HONORS_GPA_THRESHOLD:
        return HONORS_CREDIT_LIMIT
    return STANDARD_CREDIT_LIMIT


def process_enrollment(conn, request):
    """The heart of the monolith: validates business rules, mutates
    shared state, writes to the database, and queues an email -- all
    in one function."""
    global running_credit_totals

    student_id = request["student_id"]
    course_code = request["course_code"]

    course = COURSE_CATALOG.get(course_code)
    if course is None:
        status = "FAILED"
        reason = "Course does not exist: " + course_code
        _record_result(conn, request, status, reason)
        _queue_email(request, status, reason)
        return status, reason

    prereq_ok, prereq_reason = check_prerequisites(
        course_code, request["completed_courses"], request["override"]
    )
    if not prereq_ok:
        status = "FAILED"
        _record_result(conn, request, status, prereq_reason)
        _queue_email(request, status, prereq_reason)
        return status, prereq_reason

    limit = get_credit_limit(request["gpa"])
    current_total = running_credit_totals.get(student_id, 0)
    new_total = current_total + course["credits"]

    if new_total > limit:
        status = "FAILED"
        reason = "Credit limit exceeded ({} > {})".format(new_total, limit)
        _record_result(conn, request, status, reason)
        _queue_email(request, status, reason)
        return status, reason

    # success path
    running_credit_totals[student_id] = new_total
    status = "SUCCESS"
    reason = prereq_reason if prereq_reason else "Enrolled successfully"
    _record_result(conn, request, status, reason)
    _queue_email(request, status, reason)
    return status, reason


def _record_result(conn, request, status, reason):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO enrollments (student_id, student_name, course_code, status, reason, processed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            request["student_id"],
            request["name"],
            request["course_code"],
            status,
            reason,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


def _queue_email(request, status, reason):
    """Pretends to send an email by appending to a global log and
    printing to stdout."""
    subject = "Enrollment {}: {}".format(status, request["course_code"])
    body = "Hi {},\n\n{}\n\nReason: {}\n".format(request["name"], subject, reason)
    email_log.append({"to": request["email"], "subject": subject, "body": body})
    print("[EMAIL SIMULATED] To: {} | Subject: {}".format(request["email"], subject))


def generate_html_report(results, path):
    """Builds the HTML report by hand, string-concatenation style,
    right next to the business logic and DB calls."""
    rows_html = ""
    success_count = 0
    fail_count = 0
    for r in results:
        css_class = "success" if r["status"] == "SUCCESS" else "failed"
        if r["status"] == "SUCCESS":
            success_count += 1
        else:
            fail_count += 1
        rows_html += """
        <tr class="{css_class}">
            <td>{student_id}</td>
            <td>{name}</td>
            <td>{course_code}</td>
            <td>{status}</td>
            <td>{reason}</td>
        </tr>
        """.format(
            css_class=css_class,
            student_id=r["student_id"],
            name=r["name"],
            course_code=r["course_code"],
            status=r["status"],
            reason=r["reason"],
        )

    html = """
    <html>
    <head>
        <title>Enrollment Report</title>
        <style>
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
            .success {{ background-color: #e6ffe6; }}
            .failed {{ background-color: #ffe6e6; }}
        </style>
    </head>
    <body>
        <h1>Enrollment Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Successful: {success_count} | Failed: {fail_count}</p>
        <table>
            <tr><th>Student ID</th><th>Name</th><th>Course</th><th>Status</th><th>Reason</th></tr>
            {rows}
        </table>
    </body>
    </html>
    """.format(
        timestamp=datetime.now().isoformat(),
        success_count=success_count,
        fail_count=fail_count,
        rows=rows_html,
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = get_connection()
    setup_database(conn)

    requests = read_requests(CSV_PATH)

    results = []
    for request in requests:
        status, reason = process_enrollment(conn, request)
        results.append(
            {
                "student_id": request["student_id"],
                "name": request["name"],
                "course_code": request["course_code"],
                "status": status,
                "reason": reason,
            }
        )

    generate_html_report(results, REPORT_PATH)
    conn.close()

    print("Processed {} enrollment requests.".format(len(results)))
    print("Report written to {}".format(REPORT_PATH))
    print("{} emails simulated.".format(len(email_log)))


if __name__ == "__main__":
    main()
