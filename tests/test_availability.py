#!/usr/bin/python3
"""Uptime boundaries use observed samples, including across midnight and restarts."""

from datetime import datetime
from pathlib import Path
import runpy
import tempfile


MONITOR = runpy.run_path(str(Path(__file__).resolve().parents[1] /
                              'files/usr/bin/smartmeter-availability'))


def equal(actual, expected):
    assert actual == expected, (actual, expected)


def check(value):
    assert value


class AvailabilityTest:
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = MONITOR['open_database'](Path(self.directory.name) / 'test.sqlite3', create=True)
        self.start = int(datetime(2026, 11, 9).timestamp())
        self.end = int(datetime(2026, 11, 10).timestamp())

    def tearDown(self):
        self.db.close()
        self.directory.cleanup()

    def run_samples(self, samples, ended=None):
        run = self.db.execute('INSERT INTO runs(started_at,ended_at) VALUES(?,?)',
                              (self.start + samples[0][0], ended)).lastrowid
        for offset, status in samples:
            MONITOR['record_sample'](self.db, run, self.start + offset, status, '', '')

    def periods(self, now=600):
        return MONITOR['availability_periods'](self.db, self.start, self.end, 60, self.start + now)

    def test_completed_and_ongoing(self):
        self.run_samples([(0, 'down'), (60, 'up'), (120, 'error'), (180, 'up'),
                          (240, 'down'), (300, 'up'), (360, 'up')])
        ongoing, completed = self.periods(400)
        equal(ongoing['ended'], None)
        equal(ongoing['duration_seconds'], 100)
        equal((completed['started_at'], completed['ended_at']),
                         (self.start + 60, self.start + 240))
        equal(completed['interrupted'], False)

    def test_midnight_preserves_full_period(self):
        self.run_samples([(-120, 'up'), (-60, 'up'), (0, 'up'), (60, 'down')])
        period, = self.periods()
        equal(period['started_at'], self.start - 120)
        equal(period['duration_seconds'], 180)

    def test_no_uptime_in_empty_or_down_only_history(self):
        equal(self.periods(), [])
        self.run_samples([(0, 'down'), (60, 'error'), (120, 'down')])
        equal(self.periods(), [])

    def test_restarts_and_stale_monitor(self):
        self.run_samples([(0, 'up'), (60, 'up')], self.start + 60)
        self.run_samples([(120, 'up'), (180, 'up')])
        periods = self.periods(600)
        equal(len(periods), 2)
        check(all(p['interrupted'] and p['duration_seconds'] == 60 for p in periods))
        equal(periods[0]['ended_at'], self.start + 180)

    def test_missing_samples_break_the_period(self):
        self.run_samples([(0, 'up'), (60, 'up'), (600, 'up'), (660, 'down')])
        recent, earlier = self.periods(700)
        equal(recent['duration_seconds'], 60)
        equal(earlier['duration_seconds'], 60)
        check(earlier['interrupted'])

    def test_previous_day_and_limited_history(self):
        self.run_samples([(-120, 'up'), (-60, 'down')], self.start - 60)
        equal(self.periods(), [])
        self.run_samples([(i * 60, 'up' if i % 2 == 0 else 'down') for i in range(64)])
        periods = self.periods(3900)
        equal(len(periods), 30)
        equal(periods[0]['started_at'], self.start + 62 * 60)


if __name__ == '__main__':
    tests = AvailabilityTest()
    names = sorted(name for name in dir(tests) if name.startswith('test_'))
    for name in names:
        tests.setUp()
        try:
            getattr(tests, name)()
        finally:
            tests.tearDown()
    print(f'{len(names)} availability tests passed')
