"""Presentation layer: turns processed results into an HTML report.

This module has no idea what a "prerequisite" or a "credit limit" is.
It only knows how to render a list of result rows as HTML.
"""

from datetime import datetime
from typing import List, TypedDict


class ReportRow(TypedDict):
    student_id: str
    name: str
    course_code: str
    status: str
    reason: str


class HtmlReportGenerator:
    def generate(self, results: List[ReportRow], path: str) -> None:
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
