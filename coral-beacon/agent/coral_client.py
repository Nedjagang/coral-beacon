import os
import subprocess


def coral_sql(sql: str) -> str:
    env = os.environ.copy()
    env["CORAL_CONFIG_DIR"] = os.getenv(
        "CORAL_CONFIG_DIR", os.path.expanduser("~/coral-hackathon")
    )
    result = subprocess.run(
        ["coral", "sql", sql],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout


def coral_sql_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return coral_sql(f.read())
