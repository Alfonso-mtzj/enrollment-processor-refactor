"""Infrastructure layer: all SQLite concerns live here and nowhere
else. This class knows nothing about credit limits, prerequisites,
or HTML -- it just persists enrollment outcomes.
"""

import sqlite3
from datetime import datetime

from domain.models import EnrollmentDecision, EnrollmentRequest


class EnrollmentDatabase:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = None

    def __enter__(self):
        self.connect()
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self):
        self._conn = sqlite3.connect(self._db_path)

    def setup(self):
        cur = self._conn.cursor()
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
        self._conn.commit()

    def record_result(
        self, request: EnrollmentRequest, decision: EnrollmentDecision
    ) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO enrollments
                (student_id, student_name, course_code, status, reason, processed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request.student_id,
                request.name,
                request.course_code,
                decision.status,
                decision.reason,
                datetime.now().isoformat(),
            ),
        )
        self._conn.commit()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
