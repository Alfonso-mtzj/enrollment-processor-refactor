"""main.py -- the clean entry point.

This is the only place that knows about *all* the layers. It wires
them together and drives the flow, but contains no business rules,
no SQL, and no HTML of its own -- that all lives in the modules it
imports.
"""

import os

from domain.catalog import CourseCatalog
from domain.enrollment_rules import CreditLedger, EnrollmentPolicy
from infrastructure.csv_reader import EnrollmentCsvReader
from infrastructure.db_manager import EnrollmentDatabase
from infrastructure.email_service import EmailNotifier
from presentation.report_generator import HtmlReportGenerator

DB_PATH = "enrollment.db"
CSV_PATH = "students.csv"
REPORT_PATH = "report.html"


def run(csv_path: str = CSV_PATH, db_path: str = DB_PATH, report_path: str = REPORT_PATH):
    if os.path.exists(db_path):
        os.remove(db_path)

    reader = EnrollmentCsvReader()
    catalog = CourseCatalog()
    policy = EnrollmentPolicy(catalog=catalog, ledger=CreditLedger())
    notifier = EmailNotifier()
    reporter = HtmlReportGenerator()

    requests = reader.read(csv_path)
    results = []

    with EnrollmentDatabase(db_path) as db:
        for request in requests:
            decision = policy.evaluate(request)
            db.record_result(request, decision)
            notifier.notify(request, decision)
            results.append(
                {
                    "student_id": request.student_id,
                    "name": request.name,
                    "course_code": request.course_code,
                    "status": decision.status,
                    "reason": decision.reason,
                }
            )

    reporter.generate(results, report_path)

    print("Processed {} enrollment requests.".format(len(results)))
    print("Report written to {}".format(report_path))
    print("{} emails simulated.".format(len(notifier.log)))

    return results


if __name__ == "__main__":
    run()
