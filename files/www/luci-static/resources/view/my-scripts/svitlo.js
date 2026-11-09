'use strict';
'require view';
'require fs';
'require poll';

const PROGRAM = '/usr/libexec/svitlo-schedule';
const SOURCE = 'https://svitlo.live/selo-novi-petrivtsi';
const LABELS = { on: 'Свет есть', off: 'Отключение', maybe: 'Возможно отключение', unknown: 'Нет данных' };
const SYMBOLS = { on: '●', off: '×', maybe: '±', unknown: '—' };
const STYLES = `
.sv-root { --sv-line:rgba(127,127,127,.28); --sv-muted:#727a82; width:100%; min-width:0; }
.sv-root * { box-sizing:border-box; }
.sv-panel { margin:18px 0; padding:16px; border:1px solid var(--sv-line); border-radius:10px; min-width:0; }
.sv-panel h3 { margin:0 0 12px; }
.sv-muted { color:var(--sv-muted); font-size:.9rem; }
.sv-toolbar,.sv-queues,.sv-legend,.sv-days { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:12px 0; }
.sv-queues button,.sv-days button { border:1px solid var(--sv-line); border-radius:7px; padding:8px 11px; background:transparent; color:inherit; cursor:pointer; }
.sv-queues button.sv-selected,.sv-days button.sv-selected { border-color:#2563eb; background:rgba(37,99,235,.12); }
.sv-queues button small { display:block; color:var(--sv-muted); font-size:11px; }
.sv-cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:16px 0; }
.sv-card { border:1px solid var(--sv-line); border-radius:10px; padding:13px 15px; }
.sv-card strong { display:block; font-size:1.4rem; line-height:1.3; margin:5px 0; }
.sv-text-off { color:#bf3434; } .sv-text-on { color:#25813f; }
.sv-badge { display:inline-block; border-radius:99px; padding:5px 10px; font-weight:600; }
.sv-on { background:#addfb9; color:#145b2b; }
.sv-off { background:#f4b9b4; color:#a01e1e; }
.sv-maybe { background:#f5d98a; color:#805800; }
.sv-unknown { background:#d8dfe5; color:#535d66; }
.sv-warning { border-left:3px solid #d69e24; padding:10px 12px; background:rgba(214,158,36,.1); margin:12px 0; }
.sv-legend { gap:14px; font-size:.85rem; }
.sv-swatch { display:inline-block; width:11px; height:11px; border-radius:2px; margin-right:5px; }
.sv-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px 18px; margin:14px 0; }
.sv-block { min-width:0; }
.sv-hours { display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:3px; font-size:11px; color:var(--sv-muted); margin-bottom:4px; }
.sv-slots { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:3px; }
.sv-slot { display:block; width:100%; min-width:0; height:30px; border:0; border-radius:3px; padding:0; cursor:pointer; font-size:12px; font-weight:600; }
.sv-slot.sv-now { outline:2px solid #2563eb; outline-offset:2px; position:relative; z-index:1; }
.sv-slot:focus-visible,.sv-queues button:focus-visible { outline:2px solid #2563eb; outline-offset:2px; }
.sv-slot.sv-picked { box-shadow:inset 0 0 0 2px #2563eb; }
.sv-actual-label { display:block; font-size:11px; color:var(--sv-muted); margin:5px 0 3px; }
.sv-fact-slot { height:10px; border:1px solid rgba(127,127,127,.15); border-radius:2px; }
.sv-detail { min-height:24px; margin:10px 0; font-size:.9rem; }
.sv-intervals { display:grid; grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); gap:8px 18px; margin:14px 0 0; }
.sv-interval { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:6px 0; border-bottom:1px solid var(--sv-line); }
.sv-table-wrap { overflow-x:auto; max-width:100%; min-width:0; }
.sv-table { width:100%; border-collapse:collapse; font-size:.9rem; }
.sv-table th,.sv-table td { padding:9px 8px; text-align:left; border-bottom:1px solid var(--sv-line); white-space:nowrap; }
.sv-table button { padding:4px 8px; }
.sv-table tr.sv-active-row { background:rgba(37,99,235,.08); }
.sv-week-grid { display:grid; grid-template-columns:32px repeat(24,minmax(18px,1fr)); gap:3px; min-width:555px; align-items:center; font-size:10px; }
.sv-heat { height:19px; width:100%; min-width:0; padding:0; border:1px solid rgba(127,127,127,.15); border-radius:2px; cursor:pointer; }
.sv-summary { display:flex; flex-wrap:wrap; gap:10px 24px; margin:10px 0; }
.sv-summary strong { display:block; font-size:1.2rem; }
.sv-root details summary { cursor:pointer; font-weight:600; margin:10px 0; }
.sv-source { overflow-wrap:anywhere; }
@media(max-width:600px) { .sv-grid { grid-template-columns:1fr; gap:12px; } .sv-panel { padding:12px; } .sv-cards { grid-template-columns:repeat(2,minmax(0,1fr)); } .sv-card { padding:10px; } .sv-card strong { font-size:1.12rem; } .sv-queues { gap:6px; } .sv-queues button { flex:1 0 64px; padding:8px; } }
`;

function clock(minute) {
	return String(Math.floor(minute / 60)).padStart(2, '0') + ':' + String(minute % 60).padStart(2, '0');
}

function hours(minutes) {
	return minutes == null ? '—' : (minutes / 60).toLocaleString('ru-RU', { maximumFractionDigits: 1 }) + ' ч';
}

function stamp(seconds) {
	return seconds ? new Date(seconds * 1000).toLocaleString('ru-RU', { timeZone: 'Europe/Kyiv', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';
}

function prettyDate(key) {
	return key ? key.split('-').reverse().join('.') : '—';
}

function kyivNow(seconds) {
	const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Kyiv', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(seconds * 1000));
	const values = {};
	parts.forEach(part => { values[part.type] = part.value; });
	return { day: values.year + '-' + values.month + '-' + values.day, minute: Number(values.hour) * 60 + Number(values.minute) };
}

function intervals(slots) {
	const result = [];
	slots.forEach((state, index) => {
		const last = result[result.length - 1];
		if (last && last.state == state) last.end = (index + 1) * 30;
		else result.push({ state: state, start: index * 30, end: (index + 1) * 30 });
	});
	return result;
}

function card(label, value, detail, state) {
	return E('div', { 'class': 'sv-card' }, [E('span', { 'class': 'sv-muted' }, label), E('strong', { 'class': state ? 'sv-text-' + state : '' }, value), E('span', { 'class': 'sv-muted' }, detail || '')]);
}

function badge(state, label) {
	return E('span', { 'class': 'sv-badge sv-' + state }, label || LABELS[state]);
}

function table(headers, rows) {
	return E('div', { 'class': 'sv-table-wrap' }, [E('table', { 'class': 'sv-table' }, [
		E('thead', [E('tr', headers.map(text => E('th', text)))]), E('tbody', rows)
	])]);
}

return view.extend({
	load: function() {
		return fs.exec_direct(PROGRAM, [], 'json').catch(error => ({ error: error.message }));
	},

	render: function(data) {
		this.data = data;
		this.queue = '1.1';
		try { this.queue = localStorage.getItem('svitlo.queue') || this.queue; } catch (_) {}
		this.day = data.today;
		this.content = E('div');
		this.refreshButton = E('button', { 'class': 'btn', 'type': 'button', 'click': () => this.refresh(true) }, 'Обновить');
		this.draw();
		poll.add(() => this.refresh(false), 60);
		return E('div', { 'class': 'sv-root' }, [
			E('style', STYLES), E('h2', 'Графики отключений'),
			E('p', { 'class': 'cbi-section-descr' }, 'Нові Петрівці · планы svitlo.live и фактическая доступность SmartMeter'),
			E('div', { 'class': 'sv-toolbar' }, [this.refreshButton, E('a', { 'href': SOURCE, 'target': '_blank', 'rel': 'noopener noreferrer' }, 'Открыть источник ↗'), E('span', { 'class': 'sv-muted' }, 'Автообновление каждые 5 минут · время Киева')]),
			this.content
		]);
	},

	refresh: function(force) {
		if (this.loading) return Promise.resolve();
		this.loading = true;
		this.refreshButton.disabled = true;
		return fs.exec_direct(PROGRAM, force ? ['refresh'] : [], 'json').then(data => {
			if (data.groups || !this.data.groups) this.data = data;
			else this.data = Object.assign({}, this.data, { error: data.error || 'Не удалось обновить данные', stale: true });
			this.draw();
		}).catch(error => {
			this.data = Object.assign({}, this.data, { error: 'Ошибка обновления: ' + error.message, stale: true });
			this.draw();
		}).finally(() => { this.loading = false; this.refreshButton.disabled = false; });
	},

	selectQueue: function(queue) {
		this.queue = queue;
		this.selectedSlot = null;
		try { localStorage.setItem('svitlo.queue', queue); } catch (_) {}
		this.draw();
	},

	draw: function() {
		const data = this.data;
		const groups = data.groups || {};
		const queues = Object.keys(groups);
		const nodes = [];
		if (data.error) nodes.push(E('div', { 'class': 'sv-warning', 'role': 'status' }, data.error + (queues.length ? ' Показан сохранённый график.' : ' Данные пока не получены.')));
		nodes.push(E('p', { 'class': 'sv-muted sv-source' }, 'Проверка источника: ' + stamp(data.checked_at) + ' · Получено: ' + stamp(data.fetched_at) + (data.source_updated ? ' · Обновлено на сайте: ' + stamp(Date.parse(data.source_updated) / 1000) : '')));
		if (queues.length) {
			if (!groups[this.queue]) this.queue = queues[0];
			const now = kyivNow(data.server_time || Date.now() / 1000);
			const dates = groups[this.queue].map(day => day.date);
			if (!dates.includes(this.day)) this.day = dates.includes(now.day) ? now.day : dates[0];
			if (!dates.includes(now.day)) nodes.push(E('div', { 'class': 'sv-warning' }, 'На сайте нет графика на сегодня. Ниже указаны даты опубликованных данных.'));
			const ranking = data.analysis && data.analysis.ranking || [];
			nodes.push(E('p', { 'class': 'sv-muted' }, 'Очередь · под номером — сходство с фактом'));
			nodes.push(E('div', { 'class': 'sv-queues', 'role': 'group', 'aria-label': 'Выбор очереди' }, queues.map(queue => {
				const row = ranking.find(item => item.queue == queue);
				return E('button', { 'type': 'button', 'class': this.queue == queue ? 'sv-selected' : '', 'aria-label': 'Очередь ' + queue, 'aria-pressed': String(this.queue == queue), 'title': row && row.score != null ? 'Сходство с фактом: ' + row.score + '%' : 'Пока недостаточно данных для сравнения', 'click': () => this.selectQueue(queue) }, [
					E('span', queue), E('small', row && row.score != null ? row.score + '%' : '—')
				]);
			})));
			nodes.push(E('div', { 'class': 'sv-days' }, groups[this.queue].map(day => {
				const delta = Math.round((Date.parse(day.date) - Date.parse(now.day)) / 86400000);
				const name = delta == 0 ? 'Сегодня' : delta == 1 ? 'Завтра' : 'График';
				return E('button', { 'type': 'button', 'class': this.day == day.date ? 'sv-selected' : '', 'aria-pressed': String(this.day == day.date), 'click': () => { this.day = day.date; this.selectedSlot = null; this.draw(); } }, name + ' · ' + prettyDate(day.date));
			})));
			const day = groups[this.queue].find(day => day.date == this.day);
			nodes.push(this.schedule(day, now));
		}
		nodes.push(this.analysisPanel());
		if (queues.length) nodes.push(this.dependenciesPanel());
		nodes.push(E('p', { 'class': 'sv-muted' }, 'План и факт показаны отдельно. Недоступность SmartMeter принята за факт отключения; пробелы и ошибки проверки не считаются отключением. Источник: svitlo.live.'));
		this.content.replaceChildren(...nodes);
	},

	schedule: function(day, now) {
		const segments = intervals(day.slots);
		const counts = { on: 0, off: 0, maybe: 0, unknown: 0 };
		day.slots.forEach(state => { counts[state] += 30; });
		const today = this.day == now.day;
		const state = today ? day.slots[Math.floor(now.minute / 30)] : null;
		const next = today ? segments.find(item => item.start > now.minute && item.state == 'off') : null;
		const analysis = this.data.analysis || {};
		const latest = analysis.latest;
		const factState = latest && latest.running ? latest.status == 'up' ? 'on' : latest.status == 'down' ? 'off' : 'unknown' : 'unknown';
		const mismatch = today && ['on', 'off'].includes(state) && ['on', 'off'].includes(factState) && state != factState;
		const actual = analysis.actual && analysis.actual[this.day];
		const detail = E('div', { 'class': 'sv-detail', 'role': 'status', 'aria-live': 'polite' }, 'Нажмите на ячейку, чтобы увидеть время и факт за этот интервал.');
		const blocks = [];
		for (let block = 0; block < 4; block++) {
			const start = block * 12;
			const cells = [];
			const facts = [];
			for (let index = start; index < start + 12; index++) {
				const text = clock(index * 30) + '–' + clock((index + 1) * 30) + ' · ' + LABELS[day.slots[index]];
				const observed = actual ? actual.slice(index * 30, (index + 1) * 30) : [];
				const on = observed.filter(state => state == 'on').length;
				const off = observed.filter(state => state == 'off').length;
				const factText = 'Факт: доступно ' + on + ' мин, недоступно ' + off + ' мин, нет данных ' + (30 - on - off) + ' мин';
				const attrs = { 'type': 'button', 'class': 'sv-slot sv-' + day.slots[index] + (today && Math.floor(now.minute / 30) == index ? ' sv-now' : '') + (this.selectedSlot == index ? ' sv-picked' : ''), 'title': text, 'aria-label': text + '. ' + factText,
					'click': ev => {
						this.selectedSlot = index;
						this.content.querySelectorAll('.sv-picked').forEach(node => node.classList.remove('sv-picked'));
						ev.currentTarget.classList.add('sv-picked');
						detail.replaceChildren(E('strong', text), E('br'), factText);
					} };
				cells.push(E('button', attrs, SYMBOLS[day.slots[index]]));
				facts.push(E('div', { 'class': 'sv-fact-slot', 'title': clock(index * 30) + ' · ' + factText, 'style': 'background:linear-gradient(to right,#38a951 0%,#38a951 ' + on / 30 * 100 + '%,#d33e3e ' + on / 30 * 100 + '%,#d33e3e ' + (on + off) / 30 * 100 + '%,#d6dde3 ' + (on + off) / 30 * 100 + '%,#d6dde3 100%)' }));
			}
			blocks.push(E('div', { 'class': 'sv-block' }, [
				E('div', { 'class': 'sv-hours' }, Array.from({ length: 6 }, (_, i) => E('span', clock(block * 360 + i * 60)))),
				E('div', { 'class': 'sv-slots' }, cells),
				E('span', { 'class': 'sv-actual-label' }, 'Факт мониторинга'), E('div', { 'class': 'sv-slots' }, facts)
			]));
		}
		return E('div', [
			E('div', { 'class': 'sv-cards' }, [
				card('Сейчас по факту', factState == 'on' ? 'Доступно' : factState == 'off' ? 'Недоступно' : 'Нет измерений', 'SmartMeter · ' + stamp(latest && latest.timestamp), factState),
				card('Сейчас по графику', today ? LABELS[state] : 'План на дату', today ? 'Очередь ' + this.queue : prettyDate(this.day), state),
				card('Отключения за день', hours(counts.off), 'Свет есть: ' + hours(counts.on)),
				card('Следующее отключение', next ? clock(next.start) : '—', next ? 'До ' + clock(next.end) : today && state == 'off' ? 'Сейчас период отключения' : 'В опубликованном плане не указано')
			]),
			E('div', { 'class': 'sv-panel' }, [
				E('h3', 'Очередь ' + this.queue + ' · ' + prettyDate(this.day)),
				mismatch ? E('div', { 'class': 'sv-warning' }, 'План и факт сейчас расходятся: по очереди ' + this.queue + ' — ' + LABELS[state].toLowerCase() + ', SmartMeter ' + (factState == 'off' ? 'недоступен.' : 'доступен.')) : E('span'),
				counts.unknown == 1440 ? E('div', { 'class': 'sv-warning' }, 'График на эту дату ещё не опубликован. Отсутствие данных не означает наличие света.') : E('p', { 'class': 'sv-muted' }, 'Одна ячейка — 30 минут. Синяя рамка отмечает текущее время. Нижняя полоса — наблюдения SmartMeter.'),
				E('p', { 'class': 'sv-muted' }, 'Возможные отключения: ' + hours(counts.maybe) + ' · Нет данных: ' + hours(counts.unknown)),
				E('div', { 'class': 'sv-legend' }, Object.keys(LABELS).map(state => E('span', [E('i', { 'class': 'sv-swatch sv-' + state }), SYMBOLS[state] + ' ' + LABELS[state]]))),
				E('div', { 'class': 'sv-grid' }, blocks), detail,
				E('div', { 'class': 'sv-intervals' }, segments.map(item => E('div', { 'class': 'sv-interval' }, [E('strong', clock(item.start) + '–' + clock(item.end)), badge(item.state)])))
			])
		]);
	},

	analysisPanel: function() {
		const a = this.data.analysis || {};
		const nodes = [E('h3', 'Определение очереди по факту')];
		if (a.error || !a.target) {
			nodes.push(E('div', { 'class': 'sv-warning' }, a.error || 'История мониторинга пока недоступна.'));
			return E('div', { 'class': 'sv-panel' }, nodes);
		}
		const latest = a.latest;
		nodes.push(E('p', ['Факт: ', E('a', { 'href': L.url('admin/services/smartmeter') }, a.target.name), ' · ', latest && latest.running ? badge(latest.status == 'up' ? 'on' : latest.status == 'down' ? 'off' : 'unknown', latest.status == 'up' ? 'Доступно' : latest.status == 'down' ? 'Недоступно' : 'Ошибка проверки') : badge('unknown', 'Нет свежих измерений'), ' · ' + stamp(latest && latest.timestamp)]));
		if (a.candidate) nodes.push(E('div', { 'class': a.confident ? 'sv-toolbar' : 'sv-warning' }, [
			E('strong', a.candidates && a.candidates.length > 1 ? 'Пока неразличимы очереди: ' + a.candidates.join(', ') : (a.confident ? 'Наиболее вероятная очередь: ' : 'Предварительно ближе всего: ') + a.candidate), ' ',
			E('button', { 'type': 'button', 'class': 'btn', 'click': () => this.selectQueue(a.candidate) }, 'Показать очередь'),
			E('div', { 'class': 'sv-muted' }, a.confident ? 'Достаточно наблюдений; отрыв от следующей очереди ' + a.margin + ' п.п.' : 'Вывод пока неустойчив: мало наблюдений, похожие очереди или низкое совпадение.')
		]));
		else nodes.push(E('div', { 'class': 'sv-warning' }, 'Для определения очереди нужны совпадающие по времени наблюдения «доступно» и «недоступно» и заранее сохранённые графики. Сбор уже идёт в фоне.'));
		nodes.push(table(['Очередь', 'Сходство с фактом', 'Сравнено', 'Дней', 'Вне плана', 'Свет при отключении'], (a.ranking || []).map(row => E('tr', { 'class': row.queue == this.queue ? 'sv-active-row' : '' }, [
			E('td', [E('button', { 'type': 'button', 'class': 'btn', 'click': () => this.selectQueue(row.queue) }, row.queue)]),
			E('td', row.score == null ? 'Недостаточно данных' : row.score + '%'), E('td', hours(row.minutes)), E('td', String(row.days)),
			E('td', hours(row.unexpected_off)), E('td', hours(row.unexpected_on))
		]))));
		nodes.push(E('details', [E('summary', 'Как определяется очередь'), E('p', { 'class': 'sv-muted' }, 'За последние 28 дней сравниваются поминутные наблюдения с последней редакцией графика, полученной до начала минуты. Сходство — среднее точности для фактических отключений и наличия света; постоянное «нет света» не даёт очереди преимущества. Неопределённые периоды, ошибки и пробелы исключены. Для устойчивого вывода нужны минимум 3 дня, 6 часов сравнений, по часу обоих состояний, сходство от 70% и отрыв от следующей очереди от 10 п.п. Это статистическая оценка, а не подтверждение официальной очереди.'),
			E('p', { 'class': 'sv-muted' }, 'Архив графиков собирается с момента включения этой функции. Старые наблюдения SmartMeter используются для закономерностей, но не сравниваются с графиками, полученными позже факта.')
		]));
		nodes.push(this.patterns(a));
		return E('div', { 'class': 'sv-panel' }, nodes);
	},

	patterns: function(a) {
		const heat = [E('span')];
		const detail = E('p', { 'class': 'sv-muted', 'role': 'status', 'aria-live': 'polite' }, 'Нажмите на ячейку, чтобы увидеть долю отключений и число наблюдений.');
		for (let hour = 0; hour < 24; hour++) heat.push(E('span', String(hour).padStart(2, '0')));
		const weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
		(a.weekdays || []).forEach((cells, day) => {
			heat.push(E('span', weekdays[day]));
			cells.forEach((cell, hour) => {
				const percent = cell.off_percent;
				const title = weekdays[day] + ' ' + clock(hour * 60) + ' · ' + (percent == null ? 'нет данных' : 'недоступно ' + percent + '% наблюдавшихся минут · дней: ' + cell.days + ' · ' + cell.minutes + ' мин');
				heat.push(E('button', { 'type': 'button', 'class': 'sv-heat', 'title': title, 'aria-label': title, 'style': 'background:' + (percent == null ? '#d6dde3' : 'hsl(' + (120 * (1 - percent / 100)) + ',58%,58%)'), 'click': () => detail.replaceChildren(title) }));
			});
		});
		const recent = (a.outages || []).slice(-5).reverse();
		return E('div', [
			E('h3', { 'style': 'margin-top:24px' }, 'Закономерности фактических отключений'),
			E('p', { 'class': 'sv-muted' }, 'Последние 28 дней · с ' + prettyDate(a.since) + ' · наблюдения за ' + a.observed_days + ' дней, ' + hours(a.observed_minutes)),
			E('div', { 'class': 'sv-summary' }, [
				E('div', [E('span', { 'class': 'sv-muted' }, 'Медиана отключения'), E('strong', hours(a.median_off_minutes)), E('small', 'Завершённых периодов ≥ 10 мин: ' + a.complete_outages)]),
				E('div', [E('span', { 'class': 'sv-muted' }, 'Медиана между отключениями'), E('strong', hours(a.median_on_minutes))]),
				E('div', [E('span', { 'class': 'sv-muted' }, 'Недоступность по наблюдениям'), E('strong', a.observed_minutes ? (100 * a.off_minutes / a.observed_minutes).toFixed(1) + '%' : '—')])
			]),
			E('p', { 'class': 'sv-muted' }, 'Повторяемость по дням недели и часам: зелёный — чаще доступно, красный — чаще недоступно, серый — нет данных. Это история, а не прогноз.'),
			E('div', { 'class': 'sv-table-wrap' }, [E('div', { 'class': 'sv-week-grid' }, heat)]),
			detail,
			E('details', [E('summary', 'Последние фактические отключения'),
				recent.length ? E('ul', recent.map(item => E('li', stamp(item.start) + ' → ' + (item.ongoing && a.latest && a.latest.running ? 'продолжается' : stamp(item.end)) + (item.interrupted || item.ongoing && !(a.latest && a.latest.running) ? ' · наблюдение прервано, время включения неизвестно' : '')))) : E('p', 'Отключений в истории пока нет.')
			])
		]);
	},

	dependenciesPanel: function() {
		const rows = this.data.dependencies && this.data.dependencies[this.queue] || [];
		return E('div', { 'class': 'sv-panel' }, [
			E('h3', 'Связи очередей · относительно ' + this.queue),
			E('p', { 'class': 'sv-muted' }, 'Сравнение опубликованных графиков на обе даты. Пересечение — доля общих отключений среди периодов, когда отключена хотя бы одна очередь. Корреляция: +1 — одинаковый рисунок, −1 — противоположный, 0 — явной связи нет. Это сходство планов, не причинная зависимость.'),
			rows.length ? table(['Очередь', 'Совпадение состояний', 'Пересечение отключений', 'Корреляция', 'Похожий рисунок со сдвигом'], rows.map(row => E('tr', [
				E('td', [E('button', { 'type': 'button', 'class': 'btn', 'click': () => this.selectQueue(row.queue) }, row.queue)]),
				E('td', row.agreement + '% · ' + hours(row.hours * 60)), E('td', row.overlap == null ? '—' : row.overlap + '%'),
				E('td', row.correlation == null ? '—' : String(row.correlation)),
				E('td', row.shift_correlation != null && row.shift_correlation >= .5 ? (row.shift_minutes > 0 ? '+' : row.shift_minutes < 0 ? '−' : '') + hours(Math.abs(row.shift_minutes)) + ' · r=' + row.shift_correlation : 'Не выражен')
			]))) : E('p', 'Для сравнения пока недостаточно опубликованных данных.'),
			E('p', { 'class': 'sv-muted' }, 'Сдвиг «+» означает, что похожие периоды другой очереди идут позже выбранной. Поиск в пределах ±6 часов без переноса через полночь; на коротком графике совпадение может быть случайным.')
		]);
	},

	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
