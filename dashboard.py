
from flask import Flask, render_template_string
from pathlib import Path
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
IST = ZoneInfo("Asia/Kolkata")


def find_database():
    databases = list(DATA_DIR.glob("*.db"))

    if not databases:
        return None

    return databases[0]


def get_dashboard_data():
    db_path = find_database()

    if db_path is None:
        return {
            "total_jobs": 0,
            "applied": 0,
            "pending": 0,
            "errors": 0,
            "applications_today": 0,
            "jobs": [],
            "applications": []
        }

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM jobs
        WHERE application_status = 'APPLIED'
    """)
    applied = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM jobs
        WHERE application_status IN
        ('NOT_APPLIED', 'READY', 'REVIEW_REQUIRED')
    """)
    pending = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM jobs
        WHERE application_status IN ('ERROR', 'FAILED')
    """)
    errors = cursor.fetchone()[0]

    today = datetime.now(IST).date()

    cursor.execute("""
        SELECT applied_at
        FROM jobs
        WHERE application_status = 'APPLIED'
        AND applied_at IS NOT NULL
    """)

    applications_today = 0

    for row in cursor.fetchall():
        try:
            applied_at = datetime.fromisoformat(
                row["applied_at"].replace("Z", "+00:00")
            )

            if applied_at.astimezone(IST).date() == today:
                applications_today += 1

        except (ValueError, AttributeError):
            continue

    cursor.execute("""
        SELECT id, company, title, location, experience,
               source, application_status, apply_method
        FROM jobs
        ORDER BY id DESC
        LIMIT 20
    """)

    jobs = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT id, company, title, location,
               recruiter_email, apply_method, applied_at
        FROM jobs
        WHERE application_status = 'APPLIED'
        ORDER BY applied_at DESC
        LIMIT 20
    """)

    applications = [dict(row) for row in cursor.fetchall()]

    connection.close()

    return {
        "total_jobs": total_jobs,
        "applied": applied,
        "pending": pending,
        "errors": errors,
        "applications_today": applications_today,
        "jobs": jobs,
        "applications": applications
    }


HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Job Automation Dashboard</title>

    <meta http-equiv="refresh" content="60">

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #f1f5f9;
            color: #1e293b;
        }

        header {
            background: #0f172a;
            color: white;
            padding: 28px;
        }

        header h1 {
            margin: 0;
        }

        header p {
            color: #cbd5e1;
        }

        .container {
            max-width: 1400px;
            margin: auto;
            padding: 25px;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 18px;
            margin-bottom: 25px;
        }

        .card,
        .section {
            background: white;
            border-radius: 12px;
            padding: 22px;
            box-shadow: 0 3px 12px #0000000d;
        }

        .card-title {
            color: #64748b;
            font-size: 14px;
        }

        .card-value {
            font-size: 30px;
            font-weight: bold;
            margin-top: 10px;
        }

        .section {
            margin-bottom: 25px;
        }

        h2 {
            margin-top: 0;
        }

        .table-wrapper {
            overflow-x: auto;
        }

        table {
            width: 100%;
            min-width: 800px;
            border-collapse: collapse;
        }

        th,
        td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }

        th {
            background: #f8fafc;
        }

        .status {
            font-weight: bold;
            font-size: 12px;
        }

        .applied {
            color: #15803d;
        }

        .pending {
            color: #b45309;
        }

        .error {
            color: #dc2626;
        }

        @media (max-width: 1000px) {
            .stats {
                grid-template-columns: repeat(3, 1fr);
            }
        }

        @media (max-width: 600px) {
            .stats {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>

<body>

<header>
    <h1>Job Automation Bot</h1>
    <p>Job Collection • Application Tracking • Email Notifications</p>
</header>

<div class="container">

    <div class="stats">

        <div class="card">
            <div class="card-title">Total Jobs</div>
            <div class="card-value">{{ total_jobs }}</div>
        </div>

        <div class="card">
            <div class="card-title">Applied</div>
            <div class="card-value">{{ applied }}</div>
        </div>

        <div class="card">
            <div class="card-title">Pending</div>
            <div class="card-value">{{ pending }}</div>
        </div>

        <div class="card">
            <div class="card-title">Errors</div>
            <div class="card-value">{{ errors }}</div>
        </div>

        <div class="card">
            <div class="card-title">Applications Today</div>
            <div class="card-value">{{ applications_today }}</div>
        </div>

    </div>


    <div class="section">

        <h2>Recent Jobs</h2>

        <div class="table-wrapper">

            <table>

                <tr>
                    <th>ID</th>
                    <th>Company</th>
                    <th>Role</th>
                    <th>Location</th>
                    <th>Experience</th>
                    <th>Status</th>
                    <th>Method</th>
                </tr>

                {% for job in jobs %}

                <tr>
                    <td>{{ job.id }}</td>
                    <td>{{ job.company }}</td>
                    <td>{{ job.title }}</td>
                    <td>{{ job.location }}</td>
                    <td>{{ job.experience or '-' }}</td>

                    <td class="status
                        {% if job.application_status == 'APPLIED' %}
                            applied
                        {% elif job.application_status in
                            ['ERROR', 'FAILED'] %}
                            error
                        {% else %}
                            pending
                        {% endif %}
                    ">
                        {{ job.application_status or '-' }}
                    </td>

                    <td>{{ job.apply_method or '-' }}</td>
                </tr>

                {% else %}

                <tr>
                    <td colspan="7">No jobs found.</td>
                </tr>

                {% endfor %}

            </table>

        </div>

    </div>


    <div class="section">

        <h2>Application History</h2>

        <div class="table-wrapper">

            <table>

                <tr>
                    <th>ID</th>
                    <th>Company</th>
                    <th>Role</th>
                    <th>Location</th>
                    <th>Recruiter</th>
                    <th>Method</th>
                    <th>Applied At</th>
                </tr>

                {% for application in applications %}

                <tr>
                    <td>{{ application.id }}</td>
                    <td>{{ application.company }}</td>
                    <td>{{ application.title }}</td>
                    <td>{{ application.location }}</td>
                    <td>{{ application.recruiter_email or '-' }}</td>
                    <td>{{ application.apply_method or '-' }}</td>
                    <td>{{ application.applied_at or '-' }}</td>
                </tr>

                {% else %}

                <tr>
                    <td colspan="7">No applications yet.</td>
                </tr>

                {% endfor %}

            </table>

        </div>

    </div>

</div>

</body>
</html>
"""


@app.route("/")
def dashboard():
    data = get_dashboard_data()
    return render_template_string(HTML, **data)


if __name__ == "__main__":
    print("Job Automation Bot Dashboard")
    print("Open http://127.0.0.1:5000")
    print("Press CTRL+C to stop.")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )