"""Archive forecasts and compare them with observed SmartMeter minutes."""

from bisect import bisect_right
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sqlite3
import time
from urllib.parse import quote

HISTORY = Path('/root/svitlo-schedule.sqlite3')
WINDOW = 28


def median(values):
    values = sorted(values)
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def archive(data, observed_at=None):
    observed_at = time.time() if observed_at is None else observed_at
    with sqlite3.connect(HISTORY, timeout=3) as db:
        db.execute('CREATE TABLE IF NOT EXISTS forecasts ('
                   'id INTEGER PRIMARY KEY, day TEXT, queue TEXT, observed_at REAL, slots TEXT)')
        db.execute('CREATE INDEX IF NOT EXISTS forecast_lookup ON forecasts(day,queue,observed_at)')
        for queue, days in data['groups'].items():
            for day in days:
                slots = json.dumps(day['slots'], separators=(',', ':'))
                last = db.execute('SELECT slots FROM forecasts WHERE day=? AND queue=? '
                                  'ORDER BY observed_at DESC,id DESC LIMIT 1', (day['date'], queue)).fetchone()
                if not last or last[0] != slots:
                    db.execute('INSERT INTO forecasts(day,queue,observed_at,slots) VALUES(?,?,?,?)',
                               (day['date'], queue, observed_at, slots))
        cutoff = (datetime.now().date() - timedelta(days=90)).isoformat()
        db.execute('DELETE FROM forecasts WHERE day < ?', (cutoff,))
    HISTORY.chmod(0o600)


def readonly(path):
    return sqlite3.connect('file:' + quote(str(path)) + '?mode=ro', uri=True, timeout=2)


def read_forecasts(cutoff):
    if not HISTORY.is_file():
        return {}
    with readonly(HISTORY) as db:
        rows = db.execute('SELECT day,queue,observed_at,slots FROM forecasts WHERE day>=? '
                          'ORDER BY observed_at,id', (cutoff,)).fetchall()
    result = {}
    for day, queue, observed_at, slots in rows:
        result.setdefault((day, queue), []).append((observed_at, json.loads(slots)))
    return result


def rank_queues(minutes, forecasts, queues):
    scores = {q: {'queue': q, 'on': 0, 'off': 0, 'on_match': 0, 'off_match': 0,
                  'retrospective_minutes': 0, 'days': set()} for q in queues}
    stamps = {key: [v[0] for v in versions] for key, versions in forecasts.items()}
    midnights = {}
    for day, minute, status in minutes:
        if day not in midnights:
            midnights[day] = datetime.strptime(day, '%Y-%m-%d')
        # mktime handles Kyiv's DST rules without requiring an IANA database.
        timestamp = (midnights[day] + timedelta(minutes=minute)).timestamp()
        for queue in queues:
            key = (day, queue)
            versions = forecasts.get(key, [])
            if not versions:
                continue
            index = bisect_right(stamps[key], timestamp) - 1
            # Later revisions must never repair earlier predictions in the rating.
            if index < 0:
                if versions[0][1][minute // 30] in ('on', 'off'):
                    scores[queue]['retrospective_minutes'] += 1
                continue
            prediction = versions[index][1][minute // 30]
            if prediction not in ('on', 'off'):
                continue
            score = scores[queue]
            score[status] += 1
            score['days'].add(day)
            if prediction == status:
                score[status + '_match'] += 1
    ranking = []
    for score in scores.values():
        score['days'] = len(score['days'])
        total = score['on'] + score['off']
        score['minutes'] = total
        score['agreement'] = round(100 * (score['on_match'] + score['off_match']) / total, 1) if total else None
        # Balanced accuracy prevents an always-off queue from winning a long outage.
        score['score'] = round(50 * (score['on_match'] / score['on'] + score['off_match'] / score['off']), 1) \
            if score['on'] and score['off'] else None
        score['unexpected_off'] = score['off'] - score['off_match']
        score['unexpected_on'] = score['on'] - score['on_match']
        ranking.append(score)
    ranking.sort(key=lambda s: (s['score'] if s['score'] is not None else -1, s['minutes']), reverse=True)
    top = ranking[0] if ranking else None
    margin = (top['score'] - ranking[1]['score']) if top and top['score'] is not None and len(ranking) > 1 \
        and ranking[1]['score'] is not None else 0
    enough = bool(top and top['days'] >= 3 and top['minutes'] >= 360 and min(top['on'], top['off']) >= 60)
    confident = bool(enough and top['score'] >= 70 and margin >= 10)
    candidates = [row['queue'] for row in ranking if top and top['score'] is not None and row['score'] == top['score']]
    return {'ranking': ranking, 'candidate': top['queue'] if top and top['score'] is not None else None,
            'candidates': candidates,
            'confident': confident, 'enough_data': enough, 'margin': round(margin, 1),
            'method': 'balanced_accuracy', 'window_days': WINDOW}


def dependencies(groups):
    result = {}
    for queue, days in groups.items():
        base = {day['date']: day['slots'] for day in days}
        relationships = []
        for other, other_days in groups.items():
            if other == queue:
                continue
            comparisons = []
            other_map = {d['date']: d['slots'] for d in other_days}
            for day, slots in base.items():
                for a, b in zip(slots, other_map.get(day, [])):
                    if a in ('on', 'off') and b in ('on', 'off'):
                        comparisons.append((int(a == 'off'), int(b == 'off')))
            if len(comparisons) < 8:
                continue
            n = len(comparisons)
            a = sum(x for x, _ in comparisons)
            b = sum(y for _, y in comparisons)
            joint = sum(x * y for x, y in comparisons)
            denominator = math.sqrt(a * (n - a) * b * (n - b))
            same = sum(x == y for x, y in comparisons)
            shifts = []
            for shift in range(-12, 13):
                pairs = [(int(x == 'off'), int(other_map[day][i + shift] == 'off'))
                         for day, slots in base.items() if day in other_map
                         for i, x in enumerate(slots) if 0 <= i + shift < 48
                         and x in ('on', 'off') and other_map[day][i + shift] in ('on', 'off')]
                if len(pairs) < 16:
                    continue
                m = len(pairs)
                x = sum(v[0] for v in pairs)
                y = sum(v[1] for v in pairs)
                denom = math.sqrt(x * (m - x) * y * (m - y))
                if denom:
                    phi = (m * sum(u * v for u, v in pairs) - x * y) / denom
                    shifts.append((phi, -abs(shift), shift, m))
            best = max(shifts) if shifts else None
            relationships.append({
                'queue': other, 'agreement': round(100 * same / n, 1),
                'overlap': round(100 * joint / (a + b - joint), 1) if a + b - joint else None,
                'correlation': round((n * joint - a * b) / denominator, 3) if denominator else None,
                'hours': n / 2,
                'shift_minutes': best[2] * 30 if best else None,
                'shift_correlation': round(best[0], 3) if best else None,
                'shift_hours_compared': best[3] / 2 if best else None,
            })
        relationships.sort(key=lambda row: abs(row['correlation'] or 0), reverse=True)
        result[queue] = relationships
    return result


def fact_analysis(target, data, now=None):
    now = time.time() if now is None else now
    today = datetime.fromtimestamp(now).date()
    cutoff = (today - timedelta(days=WINDOW - 1)).isoformat()
    result = {'target': {'id': target['id'], 'name': target['name'], 'type': target['type']},
              'window_days': WINDOW, 'since': cutoff, 'today': today.isoformat()}
    path = Path(target['database'])
    if not path.is_file():
        return {**result, 'error': 'У выбранного мониторинга ещё нет истории'}
    with readonly(path) as db:
        rows = db.execute('SELECT day,minute_of_day,up_samples,down_samples FROM minutes '
                          'WHERE day>=? AND day<=? ORDER BY day,minute_of_day', (cutoff, today.isoformat())).fetchall()
        latest = db.execute('SELECT s.ts,s.status,r.ended_at FROM samples s JOIN runs r ON r.id=s.run_id '
                            'ORDER BY s.id DESC LIMIT 1').fetchone()
        outages = db.execute('SELECT started_at,ended_at,last_down_at,interrupted,run_id FROM outages '
                             'WHERE started_at>=? ORDER BY started_at',
                             (datetime.strptime(cutoff, '%Y-%m-%d').timestamp(),)).fetchall()
    minutes = []
    actual = {}
    by_slot = [[0, 0, set()] for _ in range(48)]
    weekdays = [[[0, 0, set()] for _ in range(24)] for _ in range(7)]
    weekday_cache = {}
    for day, minute, up, down in rows:
        if up == down or not 0 <= minute < 1440:
            continue
        status = 'on' if up > down else 'off'
        minutes.append((day, minute, status))
        if day >= (today - timedelta(days=1)).isoformat():
            actual.setdefault(day, ['unknown'] * 1440)[minute] = status
        by_slot[minute // 30][status == 'off'] += 1
        by_slot[minute // 30][2].add(day)
        weekday = weekday_cache.setdefault(day, datetime.strptime(day, '%Y-%m-%d').weekday())
        cell = weekdays[weekday][minute // 60]
        cell[status == 'off'] += 1
        cell[2].add(day)
    def probability(cell):
        on, off, days = cell
        total = on + off
        return {'off_percent': round(100 * off / total, 1) if total else None,
                'minutes': total, 'days': len(days)}
    complete = [(start, end) for start, end, _, interrupted, _ in outages
                if end and not interrupted and end - start >= 600]
    rests = [outages[i + 1][0] - item[1] for i, item in enumerate(outages[:-1])
             if item[1] and not item[3] and not outages[i + 1][3]
             and item[4] == outages[i + 1][4]
             and outages[i + 1][0] - item[1] >= 600]
    intervals = []
    # Invalid or interrupted runs never provide an inferred restoration time.
    for start, end, last_down, interrupted, _ in outages[-20:]:
        intervals.append({'start': start, 'end': end if not interrupted else last_down,
                          'interrupted': bool(interrupted), 'ongoing': end is None and not interrupted})
    result.update({
        'actual': actual, 'observed_days': len({row[0] for row in minutes}),
        'observed_minutes': len(minutes), 'off_minutes': sum(row[2] == 'off' for row in minutes),
        'latest': {'timestamp': latest[0], 'status': latest[1],
                   'running': target.get('enabled') == '1' and latest[2] is None and
                   now - latest[0] <= max(60, int(target['interval']) * 3)} if latest else None,
        'hourly': [probability(cell) for cell in by_slot],
        'weekdays': [[probability(cell) for cell in cells] for cells in weekdays],
        'median_off_minutes': round(median((end - start) / 60 for start, end in complete)) if complete else None,
        'complete_outages': len(complete),
        'median_on_minutes': round(median(rests) / 60) if rests else None,
        'outages': intervals,
        **rank_queues(minutes, read_forecasts(cutoff), data.get('groups', {}).keys()),
    })
    return result
