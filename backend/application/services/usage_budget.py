"""Atomic SQLite quotas shared by lab and legacy calls in this process.

Counters survive service restarts on a retained disk. Render's free ephemeral
filesystem may reset on redeploy, so this is a usage brake, not billing control.
No raw addresses, recordings or credentials are stored.
"""
import hashlib
import os
import sqlite3
import tempfile
import time
from pathlib import Path


class BudgetExceeded(Exception):
    pass


class UsageBudget:
    def __init__(self, path=None, daily=None, per_client=None, starts=None):
        self.path = path or os.getenv("VOICEOPS_BUDGET_PATH", str(Path(tempfile.gettempdir()) / "voiceops-usage.sqlite3"))
        self.daily = daily if daily is not None else int(os.getenv("VOICEOPS_DAILY_TRIALS", "300"))
        self.per_client = per_client if per_client is not None else int(os.getenv("VOICEOPS_CLIENT_DAILY_TRIALS", "150"))
        self.starts = starts if starts is not None else int(os.getenv("VOICEOPS_STARTS_PER_10_MIN", "12"))

    def reserve(self, client, count, now=None):
        now = int(time.time() if now is None else now)
        day, window = now // 86400, now // 600
        identity = hashlib.sha256((str(day) + ":" + client).encode()).hexdigest()
        entries = [("global", day, count, self.daily), (identity, day, count, self.per_client),
                   (identity + ":starts", window, 1, self.starts)]
        with sqlite3.connect(self.path, timeout=3) as db:
            db.execute("CREATE TABLE IF NOT EXISTS usage (bucket TEXT, period INTEGER, count INTEGER, PRIMARY KEY(bucket, period))")
            db.execute("BEGIN IMMEDIATE")
            for bucket, period, amount, limit in entries:
                used = db.execute("SELECT count FROM usage WHERE bucket=? AND period=?", (bucket, period)).fetchone()
                if (used[0] if used else 0) + amount > limit:
                    raise BudgetExceeded("Demo usage limit reached. Try a smaller experiment or return after the limit resets.")
            for bucket, period, amount, limit in entries:
                db.execute("INSERT INTO usage VALUES(?,?,?) ON CONFLICT(bucket,period) DO UPDATE SET count=count+excluded.count", (bucket, period, amount))
            db.execute("DELETE FROM usage WHERE (bucket LIKE '%:starts' AND period < ?) OR (bucket NOT LIKE '%:starts' AND period < ?)", (window-1, day-1))
        return {"reserved_trials": count, "server_daily_limit": self.daily, "client_daily_limit": self.per_client}


usage_budget = UsageBudget()
