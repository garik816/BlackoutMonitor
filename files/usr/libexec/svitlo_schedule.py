#!/usr/bin/python3
"""Fixed-source Svitlo.live adapter for LuCI; no user supplied URLs or commands."""

from datetime import datetime
import fcntl
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import sqlite3

from smartmeter_config import read_targets
from svitlo_analysis import archive, dependencies, fact_analysis

SOURCE = "https://svitlo.live/selo-novi-petrivtsi"
CACHE_DIR = Path("/tmp/svitlo-schedule")
TTL = 300
RETRY = 60
GROUPS = [f"{n}.{part}" for n in range(1, 7) for part in (1, 2)]
# The source CSS paints these classes from left to right, one half-hour each.
STATES = {
    "on": ("on", "on"), "off": ("off", "off"),
    "temp": ("maybe", "maybe"), "noinfo": ("unknown", "unknown"),
    "f1": ("off", "maybe"), "f2": ("maybe", "on"),
    "f3": ("off", "maybe"), "f4": ("off", "on"), "f5": ("on", "off"),
}


class ScheduleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.updated = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "last-modified":
            self.updated = attrs.get("content")
        if tag == "table" and "graph" in attrs.get("class", "").split():
            self.table = []
        elif self.table is not None and tag == "tr":
            self.row = []
        elif self.row is not None and tag in ("td", "th"):
            self.cell = {"text": "", "classes": attrs.get("class", "").split()}

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_schedule(html):
    parser = ScheduleParser()
    parser.feed(html)
    groups = {group: [] for group in GROUPS}
    for table in parser.tables:
        if len(table) != 2 or any(len(row) != 25 for row in table):
            raise ValueError("Структура графика на сайте изменилась")
        header, row = table
        day = datetime.strptime(header[0]["text"].strip(), "%d.%m.%Y").date().isoformat()
        match = re.fullmatch(r"Черга\s+([1-6]\.[12])", row[0]["text"].strip())
        if not match:
            raise ValueError("Не удалось определить очередь")
        slots = []
        for hour, cell in enumerate(row[1:]):
            if header[hour + 1]["text"].strip() != f"{hour:02}:00":
                raise ValueError("Изменился формат времени на сайте")
            kinds = [kind for kind in cell["classes"] if kind in STATES]
            # Unknown markup must never be interpreted as available electricity.
            if len(kinds) != 1:
                raise ValueError("Неизвестное обозначение в графике")
            slots.extend(STATES[kinds[0]])
        group = match[1]
        if any(item["date"] == day for item in groups[group]):
            raise ValueError("Повтор даты в графике")
        groups[group].append({"date": day, "slots": slots})
    if any(len(days) != 2 for days in groups.values()):
        raise ValueError("Сайт вернул неполный набор очередей")
    date_sets = {tuple(sorted(day["date"] for day in days)) for days in groups.values()}
    if len(date_sets) != 1:
        raise ValueError("Даты очередей на сайте не совпадают")
    for days in groups.values():
        days.sort(key=lambda day: day["date"])
    return {"groups": groups, "source_updated": parser.updated}


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def write_json(path, value):
    temporary = path.with_suffix(".new")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    temporary.replace(path)


def fetch_schedule():
    result = subprocess.run([
        "/usr/bin/curl", "--fail", "--silent", "--show-error", "--location",
        "--max-redirs", "3", "--proto", "=https", "--proto-redir", "=https",
        "--connect-timeout", "5", "--max-time", "18", "--max-filesize", "2097152",
        "--user-agent", "Mozilla/5.0", SOURCE,
    ], capture_output=True, timeout=20, check=False)
    if result.returncode:
        raise RuntimeError("Сайт svitlo.live недоступен. Повторная проверка через минуту.")
    return parse_schedule(result.stdout.decode("utf-8"))


def get_data(force=False):
    CACHE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (CACHE_DIR / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cached = read_json(CACHE_DIR / "data.json")
        attempt = read_json(CACHE_DIR / "attempt.json")
        now = time.time()
        age = now - cached.get("fetched_at", 0)
        elapsed = now - attempt.get("checked_at", 0)
        if (age >= TTL or age < 0 or force) and (elapsed >= RETRY or elapsed < 0):
            attempt = {"checked_at": now}
            try:
                cached = {**fetch_schedule(), "fetched_at": time.time()}
                archive(cached, cached['fetched_at'])
                write_json(CACHE_DIR / "data.json", cached)
            except (ValueError, RuntimeError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
                attempt["error"] = str(exc)
            write_json(CACHE_DIR / "attempt.json", attempt)
        return {
            **cached, "source": SOURCE, "location": "Нові Петрівці",
            "server_time": time.time(), "today": datetime.now().date().isoformat(),
            "checked_at": attempt.get("checked_at"), "error": attempt.get("error"),
            "stale": bool(attempt.get("error")) or time.time() - cached.get("fetched_at", 0) > TTL * 2,
            "refresh_seconds": TTL,
        }


def ensure_timezone():
    # OpenWrt supplies POSIX timezone rules rather than the optional IANA database.
    timezone = "EET-2EEST,M3.5.0/3,M10.5.0/4"
    if os.environ.get('TZ') != timezone:
        os.environ['TZ'] = timezone
        # OpenWrt's small Python build can omit time.tzset().
        os.execv(sys.executable, [sys.executable, sys.argv[0], *sys.argv[1:]])


def watch():
    ensure_timezone()
    while True:
        try:
            data = get_data()
            deadline = data.get('checked_at', 0) + RETRY if data.get('error') else data.get('fetched_at', 0) + TTL
            delay = max(1, min(TTL, deadline - time.time()))
        except (OSError, ValueError, sqlite3.Error) as exc:
            print(str(exc), file=sys.stderr, flush=True)
            delay = RETRY
        time.sleep(delay)


def main():
    ensure_timezone()
    try:
        if sys.argv[1:] not in ([], ["refresh"]):
            raise ValueError("Недопустимые параметры")
        data = get_data(sys.argv[1:] == ["refresh"])
        data['dependencies'] = dependencies(data.get('groups', {}))
        try:
            targets = read_targets()
            target = next((item for item in targets if item['id'] == 'main'), None)
            if target:
                data['analysis'] = fact_analysis(target, data)
            else:
                data['analysis'] = {'error': 'Основная проверка SmartMeter не настроена'}
        except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
            data['analysis'] = {'error': 'Не удалось прочитать историю мониторинга: ' + str(exc)}
    except (OSError, ValueError) as exc:
        data = {"source": SOURCE, "error": str(exc), "server_time": time.time()}
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
