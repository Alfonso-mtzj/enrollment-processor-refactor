"""Infrastructure layer: reads the (messy) enrollment request CSV and
turns each row into a clean domain.EnrollmentRequest.

All the "ugly data" cleanup lives here, on purpose -- it's an
infrastructure concern (adapting an external file format), not a
business rule.
"""

import csv
from typing import List

from domain.models import EnrollmentRequest


def _clean_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_bool_flag(value) -> bool:
    return _clean_str(value).lower() in ("y", "yes", "true", "1")


class EnrollmentCsvReader:
    def read(self, path: str) -> List[EnrollmentRequest]:
        requests = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            normalized_fieldnames = {
                name: name.strip().lower().replace(" ", "_")
                for name in reader.fieldnames
            }
            for raw_row in reader:
                row = {normalized_fieldnames[k]: v for k, v in raw_row.items()}

                student_id = _clean_str(row.get("student_id"))
                if not student_id:
                    continue  # skip unusable rows, same as the legacy behavior

                name = _clean_str(row.get("name")) or "Unknown Student"
                email = _clean_str(row.get("email")).lower()
                course_code = _clean_str(row.get("course_code")).upper()

                gpa_raw = _clean_str(row.get("gpa"))
                try:
                    gpa = float(gpa_raw) if gpa_raw else 0.0
                except ValueError:
                    gpa = 0.0

                completed_raw = _clean_str(row.get("completed_courses"))
                completed_courses = (
                    [c.strip().upper() for c in completed_raw.split("|") if c.strip()]
                    if completed_raw
                    else []
                )

                override = _parse_bool_flag(row.get("override_prereq"))

                requests.append(
                    EnrollmentRequest(
                        student_id=student_id,
                        name=name,
                        email=email,
                        gpa=gpa,
                        completed_courses=completed_courses,
                        course_code=course_code,
                        override_prereq=override,
                    )
                )
        return requests
