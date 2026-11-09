#!/usr/bin/python3
"""Deterministic tests; all databases and HTTP/cache fixtures stay in /tmp."""

from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

LIB = Path(__file__).resolve().parents[1] / 'files/usr/libexec'
sys.path.insert(0, str(LIB))
import svitlo_analysis as analysis

import svitlo_schedule as schedule


def check(value, message):
    if not value:
        raise AssertionError(message)


def fixture(classes=None):
    classes = classes or ['on'] * 24
    result = ['<meta name="last-modified" content="2026-11-09T01:00:00+02:00">']
    for group in schedule.GROUPS:
        for day in ('09.11.2026', '10.11.2026'):
            result.append('<table class="graph"><tr><td>' + day + '</td>' +
                          ''.join(f'<td>{hour:02}:00</td>' for hour in range(24)) +
                          f'</tr><tr><td>Черга {group}</td>' +
                          ''.join(f'<td class="{kind}">%</td>' for kind in classes) + '</tr></table>')
    return ''.join(result)


def test_parser():
    data = schedule.parse_schedule(fixture(['f1', 'f2', 'f3', 'f4', 'f5', 'temp', 'noinfo'] + ['on'] * 17))
    check(len(data['groups']) == 12, 'all queues')
    slots = data['groups']['1.1'][0]['slots']
    check(slots[:14] == ['off', 'maybe', 'maybe', 'on', 'off', 'maybe', 'off', 'on', 'on', 'off', 'maybe', 'maybe', 'unknown', 'unknown'], 'CSS half-hour meanings')
    for html in ('<html>challenge</html>', fixture(['new-class'] * 24), fixture().replace('00:00', '00:30'), fixture().replace('10.11.2026', '09.11.2026')):
        try:
            schedule.parse_schedule(html)
        except ValueError:
            pass
        else:
            raise AssertionError('unsafe markup accepted')


def test_rating():
    minutes, forecasts = [], {}
    for offset in range(3):
        day = (datetime(2026, 11, 1) + timedelta(days=offset)).date().isoformat()
        start = datetime.strptime(day, '%Y-%m-%d').timestamp()
        minutes += [(day, i, 'on' if i < 720 else 'off') for i in range(1440)]
        forecasts[(day, 'good')] = [(start - 1, ['on'] * 24 + ['off'] * 24)]
        forecasts[(day, 'inverse')] = [(start - 1, ['off'] * 24 + ['on'] * 24)]
        forecasts[(day, 'always_off')] = [(start - 1, ['off'] * 48)]
    rating = analysis.rank_queues(minutes, forecasts, ['good', 'inverse', 'always_off'])
    check(rating['candidate'] == 'good' and rating['confident'], 'clear queue identified')
    scores = {r['queue']: r['score'] for r in rating['ranking']}
    check(scores == {'good': 100.0, 'always_off': 50.0, 'inverse': 0.0}, 'balanced score')
    tied = dict(forecasts)
    for (day, queue), values in forecasts.items():
        if queue == 'good':
            tied[(day, 'tie')] = values
    tied_rating = analysis.rank_queues(minutes, tied, ['good', 'tie'])
    check(not tied_rating['confident'] and len(tied_rating['candidates']) == 2, 'equal queues remain ambiguous')
    later = {(day, queue): [(values[0][0] + 100000, values[0][1])] for (day, queue), values in forecasts.items()}
    result = analysis.rank_queues(minutes, later, ['good', 'inverse'])
    check(result['candidate'] is None and result['ranking'][0]['minutes'] == 0, 'no retrospective leakage')
    only_down = [row for row in minutes if row[2] == 'off']
    check(analysis.rank_queues(only_down, forecasts, ['good', 'inverse'])['candidate'] is None, 'both actual states required')
    day = '2026-11-01'
    midnight = datetime.strptime(day, '%Y-%m-%d').timestamp()
    revisions = {(day, 'q'): [(midnight - 1, ['on'] * 48), (midnight + 3600, ['off'] * 48)]}
    rows = [(day, m, 'off') for m in range(120)]
    score = analysis.rank_queues(rows, revisions, ['q'])['ranking'][0]
    check(score['off_match'] == 60, 'revision used only after it was observed')


def test_dependencies():
    groups = {q: [{'date': '2026-11-09', 'slots': slots}] for q, slots in {
        'a': ['on'] * 24 + ['off'] * 24, 'same': ['on'] * 24 + ['off'] * 24,
        'inverse': ['off'] * 24 + ['on'] * 24, 'unknown': ['unknown'] * 48}.items()}
    rows = {row['queue']: row for row in analysis.dependencies(groups)['a']}
    check(rows['same']['correlation'] == 1 and rows['same']['overlap'] == 100, 'matching patterns')
    check(rows['inverse']['correlation'] == -1 and rows['inverse']['overlap'] == 0, 'opposite patterns')
    check('unknown' not in rows, 'unknown data excluded')


def test_archive_and_actual(root):
    analysis.HISTORY = root / 'history.sqlite3'
    data = schedule.parse_schedule(fixture())
    analysis.archive(data, 100)
    analysis.archive(data, 101)
    with analysis.readonly(analysis.HISTORY) as db:
        check(db.execute('SELECT count(*) FROM forecasts').fetchone()[0] == 24, 'unchanged schedules not duplicated')
    data['groups']['1.1'][0]['slots'][0] = 'off'
    analysis.archive(data, 200)
    data['groups']['1.1'][0]['slots'][0] = 'on'
    analysis.archive(data, 300)
    with analysis.readonly(analysis.HISTORY) as db:
        check(db.execute('SELECT count(*) FROM forecasts').fetchone()[0] == 26, 'A-B-A revisions retain chronology')
    path = root / 'monitor.sqlite3'
    now = datetime(2026, 11, 9, 10).timestamp()
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE minutes(day TEXT,minute_of_day INTEGER,up_samples INTEGER,down_samples INTEGER);'
                         'CREATE TABLE runs(id INTEGER,ended_at INTEGER);'
                         'CREATE TABLE samples(id INTEGER,run_id INTEGER,ts INTEGER,status TEXT);'
                         'CREATE TABLE outages(started_at INTEGER,ended_at INTEGER,last_down_at INTEGER,interrupted INTEGER,run_id INTEGER);')
        db.executemany('INSERT INTO minutes VALUES(?,?,?,?)', [('2026-11-09', 1, 1, 0), ('2026-11-09', 2, 0, 1),
                        ('2026-11-09', 3, 0, 0), ('2026-11-09', 4, 1, 1)])
        db.execute('INSERT INTO runs VALUES(1,NULL)')
        db.execute('INSERT INTO samples VALUES(1,1,?,"down")', (now - 10,))
        db.executemany('INSERT INTO outages VALUES(?,?,?,?,?)', [(now-9000,now-8000,now-8000,0,1),
                       (now-6000,now-5000,now-5000,0,2)])
    result = analysis.fact_analysis({'id': 'main', 'name': 'Sensor', 'type': 'arp', 'enabled': '1', 'interval': '60', 'database': str(path)}, data, now)
    check(result['observed_minutes'] == 2, 'errors and ties excluded')
    check(result['actual']['2026-11-09'][:5] == ['unknown', 'on', 'off', 'unknown', 'unknown'], 'no invented states across missing minutes')
    check(result['latest']['running'], 'live monitor recognized')
    check(result['median_on_minutes'] is None, 'no inferred uptime across different runs')
    check(result['complete_outages'] == 2, 'completed outages counted')
    result = analysis.fact_analysis({'id': 'main', 'name': 'Sensor', 'type': 'arp', 'enabled': '0', 'interval': '60', 'database': str(path)}, data, now)
    check(not result['latest']['running'], 'disabled monitor never shown live')


def test_cache(root):
    schedule.CACHE_DIR = root / 'cache'
    original_fetch, original_archive, original_time = schedule.fetch_schedule, schedule.archive, schedule.time.time
    calls = []
    tick = [1000.0]
    schedule.time.time = lambda: tick[0]
    schedule.archive = lambda *args: None
    def fetch():
        calls.append(1)
        return schedule.parse_schedule(fixture())
    schedule.fetch_schedule = fetch
    try:
        first = schedule.get_data()
        check('groups' in first and not first['error'], 'initial fetch')
        schedule.get_data(True)
        check(len(calls) == 1, 'manual refresh throttled')
        tick[0] += 301
        def fail():
            raise RuntimeError('HTTP failure')
        schedule.fetch_schedule = fail
        fallback = schedule.get_data()
        check(fallback['groups'] == first['groups'] and fallback['stale'] and fallback['error'], 'last good cache survives HTTP failure')
        schedule.fetch_schedule = fetch
        schedule.get_data(True)
        check(len(calls) == 1, 'failure retry throttled')
        tick[0] += 61
        restored = schedule.get_data(True)
        check(not restored['error'] and len(calls) == 2, 'recovery clears error')
    finally:
        schedule.fetch_schedule, schedule.archive, schedule.time.time = original_fetch, original_archive, original_time


def test_entrypoint_and_collector():
    for args in (['watch'], ['refresh', 'extra'], ['https://example.invalid']):
        process = subprocess.run([sys.executable, str(LIB / 'svitlo-schedule'), *args],
                                 capture_output=True, text=True, timeout=5, check=True)
        check(json.loads(process.stdout).get('error') == 'Недопустимые параметры', 'web entrypoint rejects service mode and untrusted arguments')
    original_get, original_zone = schedule.get_data, schedule.ensure_timezone
    original_sleep, original_time = schedule.time.sleep, schedule.time.time
    delays = []
    class StopCollector(Exception):
        pass
    def sleep(delay):
        delays.append(delay)
        raise StopCollector()
    try:
        schedule.ensure_timezone = lambda: None
        schedule.time.time = lambda: 1000.0
        schedule.time.sleep = sleep
        for result in ({'fetched_at': 1000}, {'error': 'HTTP failure', 'checked_at': 1000}):
            schedule.get_data = lambda: result
            try:
                schedule.watch()
            except StopCollector:
                pass
        check(delays == [300, 60], 'background cadence and failure retry')
    finally:
        schedule.get_data, schedule.ensure_timezone = original_get, original_zone
        schedule.time.sleep, schedule.time.time = original_sleep, original_time


if __name__ == '__main__':
    test_parser()
    test_rating()
    test_dependencies()
    with tempfile.TemporaryDirectory(prefix='svitlo-tests-') as folder:
        root = Path(folder)
        test_archive_and_actual(root)
        test_cache(root)
    test_entrypoint_and_collector()
    print('PASS: parser, half-hour transitions, strict markup, balanced queue rating, ambiguous queues, revision chronology, forecast leakage, dependencies, gaps/errors, stopped monitors, archive deduplication, HTTP fallback and throttling')
