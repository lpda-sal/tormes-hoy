"""Static checks of the web app (no browser needed)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "web"


def _js_files() -> list[Path]:
    return [p for p in WEB.rglob("*.js") if "vendor" not in p.parts]


def test_service_worker_shell_files_exist() -> None:
    source = (WEB / "sw.js").read_text(encoding="utf-8")
    block = re.search(r"const SHELL = \[(.*?)\];", source, re.S)
    assert block is not None
    files = re.findall(r'"([^"]+)"', block.group(1))
    missing = [f for f in files if f != "./" and not (WEB / f).exists()]
    assert missing == []


def test_every_translation_key_exists() -> None:
    strings = json.loads((WEB / "i18n" / "es.json").read_text("utf-8"))

    def has(key: str) -> bool:
        node: object = strings
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return isinstance(node, str)

    keys = {
        key
        for path in _js_files()
        for key in re.findall(r'\bt\("([\w.]+)"', path.read_text("utf-8"))
    }
    assert keys, "no t() calls found"
    assert sorted(k for k in keys if not has(k)) == []


def test_chartjs_is_only_used_by_the_wrapper() -> None:
    users = [
        p.name for p in _js_files() if "window.Chart" in p.read_text("utf-8")
    ]
    assert users == ["charts.js"]


def test_home_and_weather_views_render() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to execute the web rendering checks")
    script = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadStrings } from './web/i18n.js';
import { clearDataCache, loadSunTimes } from './web/data.js';
import { render, renderSun, renderCsck } from './web/views/home.js';
import { render as renderWeather, renderDays } from './web/views/weather.js';
import { render as renderUv } from './web/views/uv.js';
import { SOURCE_COLORS, UV_COLORS } from './web/format.js';

let now = new Date('2026-10-08T12:00:00+02:00');
const NativeDate = Date;
globalThis.Date = class extends NativeDate {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now.getTime(); }
};
const strings = JSON.parse(readFileSync('web/i18n/es.json', 'utf8'));
const summary = JSON.parse(readFileSync('data/summary.json', 'utf8'));
summary.generated_at = '2026-10-08T15:37:48Z';
summary.location.timezone = 'Europe/Madrid';
summary.weather_now = {status: 'ok', data: {
    ...summary.weather_now.data, wind_gust: 26,
}};
const gustLabel = (value) => strings.home.wind_gust.replace('{v}',
    strings.units.wind.replace('{v}', value));
summary.today = {status: 'ok', data: Array.from({length: 10}, (_, index) => ({
    time: `2026-10-08T${String(12 + index).padStart(2, '0')}:00`,
    temperature: 20, precipitation_probability: index * 5, weather_code: 0,
}))};
summary.next_days = {status: 'ok', data: [{
    date: '2026-10-08', sunrise: '2026-10-08T08:26',
    sunset: '2026-10-08T19:53',
}]};
const weather = {forecasts: {openmeteo: {status: 'ok', data: {daily: [{
    date: '2026-10-09', temperature_max: 24, temperature_min: 10,
    precipitation_probability: 5,
}]}}}};
weather.forecasts.openmeteo.data.hourly = Array.from({length: 28},
    (_, index) => {
        const hour = 10 + index;
        const day = hour < 24 ? '2026-10-08' : '2026-10-09';
        return {time: `${day}T${String(hour % 24).padStart(2, '0')}:00`,
            temperature: 20, precipitation_probability: index * 4,
            weather_code: 0};
    });
summary.river.flow_status = 'safe';
summary.river.data.trend = 'falling';
summary.uv.data = {now: 3, max: 5, max_time: '15:00',
    protection: {from: '12:32', to: '17:30'}};
let solarCalls = 0;
let solarFailure = false;
let uvFailure = false;
const uvFile = {location: summary.location, status: 'ok',
generated_at: summary.generated_at, source: {label: 'Open-Meteo'},
data: {date: '2026-10-08', now: 3, max: 5,
protection: {from: '12:32', to: '17:30'}, hourly: [
    {time: '2026-10-08T00:00', uv: 0},
    {time: '2026-10-08T12:00', uv: 5},
    {time: '2026-10-08T23:00', uv: 0},
]}};
let savedSolar = null;
globalThis.localStorage = {
    getItem: () => savedSolar,
    setItem: (_, value) => { savedSolar = value; },
};
const solar = {
    date: '2026-10-08',
    civil_twilight_begin: '2026-10-08T06:00:00+00:00',
    sunrise: '2026-10-08T06:26:00+00:00',
    sunset: '2026-10-08T17:53:00+00:00',
    civil_twilight_end: '2026-10-08T18:20:00+00:00',
    nautical_twilight_begin: '2026-10-08T05:27:00+00:00',
    nautical_twilight_end: '2026-10-08T18:52:00+00:00',
    astronomical_twilight_begin: '2026-10-08T04:55:00+00:00',
    astronomical_twilight_end: '2026-10-08T19:24:00+00:00',
};
globalThis.fetch = async (url) => {
    if (String(url).includes('uv.json')) {
        if (uvFailure) throw new Error('UV file unavailable');
        return {ok: true, json: async () => uvFile};
    }
    if (String(url).includes('api.sunrise-sunset.org')) {
        solarCalls++;
        const params = new URL(url).searchParams;
        assert.equal(params.get('date'), '2026-10-08');
        assert.equal(params.get('tz'), 'Europe/Madrid');
        assert.equal(params.get('lat'), String(summary.location.lat));
        assert.equal(params.get('lng'), String(summary.location.lon));
        if (solarFailure) throw new Error('offline');
        return {ok: true, json: async () => solar};
    }
    return {ok: true, json: async () =>
    String(url).includes('i18n') ? strings :
    String(url).includes('summary') ? summary : weather,
    };
};
await loadStrings('es');
const chartSpecs = [];
globalThis.window = {Chart: class {
    constructor(_canvas, spec) { chartSpecs.push(spec); }
    destroy() {}
}};
globalThis.getComputedStyle = () => ({getPropertyValue: () => ''});
globalThis.document = {
    documentElement: {},
    createElement: () => ({
        style: {}, setAttribute() {}, appendChild() {}, append() {},
    }),
};
const containers = Object.fromEntries([
    '#home-rain-chart', '#home-uv-chart',
    '#temp-chart', '#rain-chart', '#humidity-chart', '#uv-chart',
].map((key) => [key, {
    innerHTML: '', replaceChildren() {},
    appendChild() { this.legendCount = (this.legendCount ?? 0) + 1; },
}]));
const solarHeader = {innerHTML: '', hidden: true};
const root = {
    innerHTML: '',
    ownerDocument: {getElementById: () => solarHeader},
    querySelector: (selector) => containers[selector],
};
await render(root);
assert.deepEqual(chartSpecs[0].data.datasets[0].data.map(p => p.y),
    Array.from({length: 24}, (_, index) => (index + 2) * 4));
const rainPoints = chartSpecs[0].data.datasets[0].data;
assert.equal(rainPoints.at(-1).x,
    new Date('2026-10-09T11:00:00+02:00').getTime());
assert.equal(chartSpecs[0].options.plugins.decorations.xRanges[0].from,
    new Date(solar.civil_twilight_end).getTime());
assert.equal(chartSpecs[0].options.plugins.decorations.xRanges[0].to,
    new Date('2026-10-09T08:00:00+02:00').getTime());
assert.equal(chartSpecs[0].options.plugins.decorations.xRanges.length, 1);
assert.equal(chartSpecs[1].options.scales.x.min,
    new Date(solar.civil_twilight_begin).getTime());
assert.equal(chartSpecs[1].options.scales.x.max,
    new Date(solar.civil_twilight_end).getTime());
assert.equal(chartSpecs[1].options.plugins.decorations.yZones.length, 5);
assert.equal(chartSpecs[1].data.datasets[0].tension, 0);
assert.equal(chartSpecs[0].options.scales.y.min, 0);
assert.equal(chartSpecs[0].options.scales.y.max, 100);
assert.equal(chartSpecs[0].options.scales.x.ticks.font.size, 11);
assert.equal(chartSpecs[0].options.scales.y.ticks.font.size, 11);
assert.equal(chartSpecs[1].options.scales.x.ticks.font.size, 11);
assert.equal(chartSpecs[1].options.scales.y.ticks.font.size, 11);
assert.equal(chartSpecs[0].data.datasets[0].borderColor,
    SOURCE_COLORS.openmeteo);
assert.equal(chartSpecs[0].options.plugins.legend.display, false);
assert.deepEqual(chartSpecs[1].data.datasets[0].data.map(p => p.y), [0, 5, 0]);
assert.equal(chartSpecs[1].options.scales.y.min, 0);
const cards = [...root.innerHTML.matchAll(
    /<a class="card(?: wide hours-card)?" href="([^"]+)">\s*<h2>([^<]+)/g,
)];
assert.deepEqual(cards.map((card) => [card[1], card[2]]), [
    ['#/weather', strings.home.weather_now],
    ['#/river', strings.home.river_now],
    ['#/weather', strings.home.rest_of_day],
]);
assert.ok(root.innerHTML.includes('id="home-rain-chart"'));
assert.ok(root.innerHTML.includes('id="home-uv-chart"'));
assert.ok(root.innerHTML.includes(strings.home.rain_hours));
assert.ok(root.innerHTML.includes('class="card wide uv-card"'));
assert.ok(root.innerHTML.includes('class="uv-summary" href="#/uv"'));
assert.equal((root.innerHTML.match(/class="hour"/g) ?? []).length, 24);
assert.ok(root.innerHTML.includes('flow-chip safe'));
assert.ok(root.innerHTML.includes('class="muted flow-status"'));
assert.ok(root.innerHTML.includes('style="background:#3ea72d;color:#111"'));
assert.ok(root.innerHTML.includes('class="muted weather-rain"'));
const details = root.innerHTML.match(
    /class="muted weather-details">([\s\S]*?)\n      <\/div>/)[1];
assert.equal((details.match(/<div/g) ?? []).length, 4);
const detailLabels = ['humidity', 'rain_amount', 'wind', 'wind_gust']
    .map(key => strings.home[key].split('{v}')[0]);
assert.ok(detailLabels.every(label => label.endsWith(': ')));
const detailPositions = detailLabels.map(label => details.indexOf(label));
assert.ok(detailPositions.every(position => position >= 0));
assert.deepEqual(detailPositions,
    [...detailPositions].sort((left, right) => left - right));
assert.ok(root.innerHTML.includes('class="muted river-reading"'));
assert.ok(root.innerHTML.includes('class="muted weather-reading"'));
assert.ok(root.innerHTML.includes('class="muted uv-at">A las 17:00'));
assert.ok(root.innerHTML.includes('class="muted river-trend"'));
assert.ok(root.innerHTML.match(/flow-chip[^>]*>[^<]*m³\/s<\/span>/));
assert.ok(!root.innerHTML.includes(strings.river.flow));
assert.match(root.innerHTML,
    /m³\/s<\/span><\/div>\s*<div class="muted flow-status">/);
assert.match(root.innerHTML,
    /class="big uv-reading"[\s\S]*class="muted uv-maximum"/);
assert.match(root.innerHTML,
    /class="uv-current">\s*<h2>[^<]*<\/h2>\s*<div class="big uv-reading"/);
assert.match(root.innerHTML,
    /class="muted uv-maximum"[\s\S]*class="uv-protection"/);
assert.ok(root.innerHTML.indexOf(strings.home.uv_max.split('{v}')[0])
    < root.innerHTML.indexOf(strings.uv.protection_label));
assert.ok(root.innerHTML.includes(
    `${strings.uv.protection_label}<br>de 12:32 a 17:30`));
assert.ok(root.innerHTML.includes('class="home-links"'));
assert.ok(root.innerHTML.includes('href="#/csck"'));
assert.ok(!root.innerHTML.includes(strings.river.level));
assert.ok(!root.innerHTML.includes('SALAMANCA/MATACAN'));
assert.ok(root.innerHTML.includes('Lluvia'));
assert.ok(root.innerHTML.includes(gustLabel('26')));
assert.match(root.innerHTML, /class="next-days-link" href="#\/weather\/days"/);
assert.ok(!root.innerHTML.includes('<table'));
assert.ok(solarHeader.innerHTML.includes('Amanecer: 08:00 - 08:26'));
assert.ok(solarHeader.innerHTML.includes('Atardecer: 19:53 - 20:20'));
assert.equal(solarHeader.hidden, false);
assert.ok(!root.innerHTML.includes('sun-times'));
assert.ok(!root.innerHTML.includes('href="https://sunrise-sunset.org/"'));
assert.ok(root.innerHTML.includes('class="card wide rain-card"'));
assert.ok(root.innerHTML.includes(
    '<a class="card wide hours-card" href="#/weather">'));
for (const [state, color] of [
    ['safe', UV_COLORS.low], ['caution', UV_COLORS.moderate],
    ['danger', UV_COLORS.very_high],
]) {
    summary.river.flow_status = state;
    await render(root);
    assert.ok(root.innerHTML.includes(`background:${color};color:#111`));
    assert.ok(root.innerHTML.includes(strings.river.flow_status[state]));
}
summary.river.flow_status = 'safe';
weather.forecasts.aemet = {status: 'ok', source: {label: 'AEMET'},
    data: {hourly: [
        {time: '2026-10-08T11:00', precipitation_probability: 99},
        {time: '2026-10-08T12:00', precipitation_probability: 25},
        {time: '2026-10-09T04:00', precipitation_probability: 35},
        {time: '2026-10-09T05:00', precipitation_probability: 99},
    ]}};
weather.forecasts.meteoblue = {status: 'stale',
    source: {label: 'Meteoblue'}, data: {hourly: [
        {time: '2026-10-08T13:00', precipitation_probability: 60},
        {time: '2026-10-08T14:00', precipitation_probability: null},
    ]}};
await render(root);
const comparison = chartSpecs.at(-2);
assert.deepEqual(comparison.data.datasets.map(series => series.borderColor),
    Object.values(SOURCE_COLORS));
assert.deepEqual(comparison.data.datasets.map(series => series.data[0].y),
    [25, 8, null]);
assert.equal(comparison.data.datasets[2].data[1].y, 60);
assert.equal(comparison.data.datasets[2].data[2].y, null);
assert.equal(comparison.data.datasets[0].data.find(point => point.x ===
    new Date('2026-10-09T04:00:00+02:00').getTime()).y, 35);
assert.equal(comparison.data.datasets[0].data.find(point => point.x ===
    new Date('2026-10-09T05:00:00+02:00').getTime()).y, 99);
assert.equal(comparison.data.datasets[0].data.at(-1).y, null);
assert.equal(comparison.options.plugins.legend.display, false);
assert.ok(root.innerHTML.includes(strings.status.stale));
const savedHourly = weather.forecasts.openmeteo.data.hourly;
weather.forecasts.openmeteo.data.hourly = [];
await render(root);
assert.equal(chartSpecs.at(-2).data.datasets.length, 2);
weather.forecasts.openmeteo.data.hourly = savedHourly;
delete weather.forecasts.aemet;
delete weather.forecasts.meteoblue;
now = new NativeDate('2026-10-08T03:30:00+02:00');
weather.forecasts.openmeteo.data.hourly = Array.from({length: 36},
    (_, index) => ({
        time: `2026-10-${index < 24 ? '08' : '09'}T`
            + `${String(index % 24).padStart(2, '0')}:00`,
        temperature: 20, precipitation_probability: 0, weather_code: 0,
    }));
await render(root);
assert.equal((root.innerHTML.match(/class="hour"/g) ?? []).length, 24);
const earlyRain = chartSpecs.at(-2);
assert.equal(earlyRain.data.datasets[0].data.at(-1).x,
    new Date('2026-10-09T02:00:00+02:00').getTime());
const earlyNights = earlyRain.options.plugins.decorations.xRanges;
assert.equal(earlyNights.length, 2);
assert.equal(earlyNights[0].to,
    new Date('2026-10-08T08:00:00+02:00').getTime());
assert.equal(earlyNights[1].from,
    new Date(solar.civil_twilight_end).getTime());
assert.equal(earlyNights[1].to,
    new Date('2026-10-09T08:00:00+02:00').getTime());
assert.equal(solarCalls, 1);
now = new NativeDate('2026-10-08T12:00:00+02:00');
weather.forecasts.openmeteo.data.hourly = savedHourly;
summary.weather_now.data.wind_gust = 0;
await render(root);
assert.ok(root.innerHTML.includes(gustLabel('0')));
delete summary.weather_now.data.wind_gust;
await render(root);
assert.ok(root.innerHTML.includes(strings.home.wind_gust.split('{v}')[0]));
assert.ok(!root.innerHTML.includes(gustLabel('0')));
assert.ok(!root.innerHTML.includes('undefined'));
const observation = summary.weather_now;
summary.weather_now = {status: 'error', data: null};
const model = summary.weather_now_model;
summary.weather_now_model = {status: 'ok', data: {
    ...observation.data, wind_gust: 24,
}};
await render(root);
assert.ok(root.innerHTML.includes(gustLabel('24')));
assert.ok(root.innerHTML.includes(strings.home.model_reading.split('{age}')[0]));
summary.weather_now = observation;
summary.weather_now_model = model;
await renderSun(root);
assert.ok(root.innerHTML.includes(strings.sun.title));
assert.ok(root.innerHTML.includes(strings.sun.civil));
assert.ok(root.innerHTML.includes(strings.sun.nautical));
assert.ok(root.innerHTML.includes(strings.sun.astronomical));
assert.ok(root.innerHTML.includes('Jueves, 8 de octubre de 2026'));
assert.ok(!root.innerHTML.includes('Salamanca'));
assert.ok(!root.innerHTML.includes('Europe/Madrid'));
assert.ok(!root.innerHTML.includes('hoy'));
assert.ok(!root.innerHTML.includes('terreno'));
const sunRows = ['sun', 'civil', 'nautical', 'astronomical']
    .map(key => root.innerHTML.indexOf(strings.sun[key]));
assert.deepEqual(sunRows, [...sunRows].sort((left, right) => left - right));
assert.ok(root.innerHTML.includes('07:27'));
assert.ok(root.innerHTML.includes('21:24'));
assert.ok(root.innerHTML.includes('Fuente: Sunrise-Sunset'));
assert.ok(!root.innerHTML.includes('sunrise-sunset.org'));
assert.ok(root.innerHTML.includes('08:00'));
await render(root);
assert.equal(solarCalls, 1);
clearDataCache();
await render(root);
assert.equal(solarCalls, 1);
summary.next_days.data[0].date = '2026-10-07';
summary.today.data = [];
weather.forecasts.openmeteo.data.hourly = [];
clearDataCache();
await render(root);
assert.ok(solarHeader.innerHTML.includes('08:00 - 08:26'));
assert.ok(root.innerHTML.includes(strings.home.no_more_hours));
assert.ok(containers['#home-rain-chart'].innerHTML
    .includes(strings.weather.no_data));
uvFailure = true;
clearDataCache();
await render(root);
assert.ok(containers['#home-uv-chart'].innerHTML
    .includes(strings.weather.no_data));
assert.ok(root.innerHTML.includes(strings.home.uv_now));
uvFailure = false;
const sourceKeys = [
    'weather_now', 'weather_now_model', 'river', 'uv', 'today',
];
for (const key of sourceKeys) {
    summary[key] = {status: 'error', data: null};
}
clearDataCache();
await render(root);
const failedCards = root.innerHTML.match(/class="card[^\"]*"/g) ?? [];
assert.equal(failedCards.length, 5);
assert.ok(root.innerHTML.includes(strings.status.error));
savedSolar = null;
solarFailure = true;
clearDataCache();
await render(root);
assert.ok(solarHeader.innerHTML.includes(strings.home.sun_unavailable));
assert.ok(root.innerHTML.includes(strings.home.weather_now));
await renderSun(root);
assert.ok(root.innerHTML.includes(strings.home.sun_unavailable));
assert.ok(root.innerHTML.includes('class="back" href="#/"'));
solarFailure = false;
solar.civil_twilight_end = 'invalid';
clearDataCache();
await assert.rejects(loadSunTimes(summary.location, '2026-10-08'));
solar.civil_twilight_end = null;
clearDataCache();
await render(root);
assert.ok(solarHeader.innerHTML.includes(strings.weather.no_data));
renderCsck(root);
assert.ok(root.innerHTML.includes(`<h1>${strings.home.csck}</h1>`));
assert.ok(root.innerHTML.includes(strings.csck.pending));
assert.ok(root.innerHTML.includes('class="back" href="#/"'));
assert.ok(readFileSync('web/app.js', 'utf8').includes('"/csck":'));
await renderDays(root);
assert.ok(root.innerHTML.includes(strings.weather.days_title));
assert.ok(root.innerHTML.includes('<table'));
assert.ok(!root.innerHTML.includes('temp-chart'));
const shell = readFileSync('web/index.html', 'utf8');
assert.match(shell, /id="sun-times" href="#\/sun"/);
assert.ok(!shell.includes('id="footer"'));

weather.location = {...summary.location};
now = new NativeDate('2026-10-08T10:30:00+02:00');
solar.civil_twilight_end = '2026-10-08T18:20:00+00:00';
savedSolar = null;
clearDataCache();
weather.observation = {status: 'ok', source: {label: 'AEMET'},
    fetched_at: '2026-10-08T10:30:00+02:00', data: {
        time: '2026-10-08T10:15:00+02:00', temperature: 18.2,
        precipitation: 0, humidity: 58,
    }};
for (const key of ['aemet', 'openmeteo', 'meteoblue']) {
    weather.forecasts[key] = {status: 'ok', source: {label: key},
        fetched_at: '2026-10-08T09:00:00+02:00', data: {hourly:
            Array.from({length: 28}, (_, index) => {
                const hour = index + 10;
                const day = hour < 24 ? '08' : '09';
                return {time: `2026-10-${day}T`
                    + `${String(hour % 24).padStart(2, '0')}:00`,
                    temperature: 18 + index, precipitation: 1.2,
                    humidity: 60, precipitation_probability: 75};
            })}};
}
await renderWeather(root);
assert.ok(root.innerHTML.includes('<h1>Tiempo</h1>'));
assert.deepEqual([...root.innerHTML.matchAll(/<h2>([^<]+)<\/h2>/g)]
    .map(match => match[1]), ['Temperatura', 'Lluvia']);
assert.ok(!root.innerHTML.includes('id="humidity-chart"'));
assert.ok(root.innerHTML.includes(
    '<p class="weather-sources-label">Fuentes:</p>'));
assert.equal((root.innerHTML.match(/class="legend"/g) ?? []).length, 1);
assert.ok(root.innerHTML.includes('Observación AEMET'));
assert.ok(root.innerHTML.includes('Actualizado hace'));
const sourceList = root.innerHTML.slice(
    root.innerHTML.indexOf('class="weather-sources"'));
const sourcePositions = [
    'Observación AEMET', 'aemet', 'openmeteo', 'meteoblue',
].map(label => sourceList.indexOf(label));
assert.ok(sourcePositions.every(position => position >= 0));
assert.deepEqual(sourcePositions,
    [...sourcePositions].sort((left, right) => left - right));
assert.match(sourceList, /\(Lectura hace [^)]+\)/);
assert.equal((sourceList.match(/\(Actualizado [^)]+\)/g) ?? []).length, 3);
assert.ok(!root.innerHTML.includes('<h2>Observación</h2>'));
assert.ok(root.innerHTML.indexOf(strings.weather.spread_note)
    < root.innerHTML.indexOf('id="temp-chart"'));
assert.ok(root.innerHTML.indexOf('id="rain-chart"')
    < root.innerHTML.indexOf('class="weather-sources-label"'));
assert.ok(root.innerHTML.indexOf('class="legend"')
    > root.innerHTML.indexOf('class="weather-sources-label"'));
assert.ok(!root.innerHTML.includes('href="#/weather/days"'));
const weatherCharts = chartSpecs.slice(-2);
const observedValues = [18.2, null];
for (const [index, spec] of weatherCharts.entries()) {
    const observed = spec.data.datasets.find(series =>
        series.showLine === false);
    if (index === 1) {
        assert.equal(observed, undefined);
        continue;
    }
    assert.equal(observed.pointRadius, 5);
    assert.equal(observed.order, -1);
    assert.equal(observed.label, 'Observación AEMET');
    const points = observed.data.filter(point => point.y !== null);
    assert.deepEqual(points, [{
        x: new Date('2026-10-08T10:15:00+02:00').getTime(),
        y: observedValues[index],
    }]);
    assert.ok(spec.options.plugins.tooltip.filter({dataset: observed,
        raw: points[0]}));
    assert.ok(spec.options.plugins.tooltip.callbacks.title([{raw: points[0]}])
        .includes('8 oct'));
    assert.equal(spec.options.scales.x.ticks.callback(points[0].x), '10:15');
    assert.equal(spec.data.datasets[0].data[0].x,
        new Date('2026-10-08T10:00:00+02:00').getTime());
    assert.equal(spec.data.datasets[0].spanGaps, 3600000);
    assert.deepEqual(spec.options.plugins.decorations.xRanges, [{
        from: new Date('2026-10-08T18:20:00+00:00').getTime(),
        to: new Date('2026-10-09T06:00:00+00:00').getTime(),
        color: '#555',
    }]);
}
assert.equal(weatherCharts[1].data.datasets[0].data[0].y, 75);
assert.equal(weatherCharts[1].options.plugins.tooltip.callbacks.label({
    dataset: weatherCharts[1].data.datasets[0], raw: {y: 75},
}), ' aemet: 75 %');
assert.equal(weatherCharts[1].options.scales.y.min, 0);
assert.equal(weatherCharts[1].options.scales.y.max, 100);
assert.equal(weatherCharts[1].options.scales.y.ticks.callback(50), '50 %');
assert.equal(weatherCharts[0].options.scales.y.ticks.callback(20), '20 °C');
for (const selector of ['#temp-chart', '#rain-chart']) {
    assert.equal(containers[selector].legendCount ?? 0, 0);
}
now = new NativeDate('2026-10-08T23:30:00+02:00');
weather.observation.data.time = '2026-10-08T23:00:00+02:00';
for (const key of ['aemet', 'openmeteo', 'meteoblue']) {
    weather.forecasts[key].data.hourly = [
        '2026-10-08T22:00', '2026-10-08T23:00',
        '2026-10-09T00:00', '2026-10-09T22:00', '2026-10-09T23:00',
    ].map(time => ({time, temperature: 19, humidity: 60,
        precipitation_probability: 30}));
}
await renderWeather(root);
const lateCharts = chartSpecs.slice(-2);
const lastReadingTime = new Date('2026-10-08T23:00:00+02:00').getTime();
assert.ok(lateCharts.every(spec => spec.options.scales.x.min
    === lastReadingTime));
assert.ok(lateCharts.every(spec => spec.options.scales.x.max ===
    new Date('2026-10-09T22:00:00+02:00').getTime()));
const lateObservation = lateCharts[0].data.datasets.find(series =>
    series.showLine === false);
assert.equal(lateObservation.data[0].x, lastReadingTime);
assert.equal(lateObservation.data[0].y, 18.2);
now = new NativeDate('2026-10-09T00:30:00+02:00');
await renderWeather(root);
assert.equal(chartSpecs.at(-2).options.scales.x.min, lastReadingTime);
assert.equal(chartSpecs.at(-2).data.datasets[0].data[0].y, 19);
assert.equal(chartSpecs.at(-2).data.datasets[0].data[1].x,
    new Date('2026-10-09T00:00:00+02:00').getTime());
weather.observation.status = 'error';
await renderWeather(root);
assert.ok(chartSpecs.slice(-2).every(spec =>
    spec.data.datasets.every(series => series.showLine !== false)));
weather.observation.status = 'stale';
weather.observation.data.time = '2026-10-07T23:15:00+02:00';
for (const key of ['aemet', 'openmeteo', 'meteoblue']) {
    weather.forecasts[key] = {status: 'error', data: null};
}
await renderWeather(root);
assert.equal(chartSpecs.at(-1).data.datasets.length, 1);
assert.ok(containers['#rain-chart'].innerHTML.includes(strings.weather.no_data));
assert.equal(chartSpecs.at(-1).data.datasets[0].data[0].x,
    new Date('2026-10-07T23:15:00+02:00').getTime());
now = new Date('2026-10-08T12:00:00+02:00');
solarFailure = false;
solar.civil_twilight_end = '2026-10-08T18:20:00+00:00';
savedSolar = null;
clearDataCache();
await renderUv(root);
assert.ok(root.innerHTML.includes('<h1>Índice UV '));
assert.ok(root.innerHTML.includes('A las 17:00'));
assert.ok(root.innerHTML.includes('uv-reading-meta'));
assert.ok(!root.innerHTML.includes('Umbral'));
assert.ok(root.innerHTML.includes(
    '<section class="card"><div id="uv-chart"></div></section>'));
assert.ok(root.innerHTML.indexOf(strings.uv.source_note)
    < root.innerHTML.indexOf('id="uv-chart"'));
assert.ok(root.innerHTML.indexOf(strings.chart_hint)
    < root.innerHTML.indexOf('id="uv-chart"'));
assert.ok(root.innerHTML.indexOf('Fuente: Open-Meteo')
    > root.innerHTML.indexOf('</section>'));
assert.equal(containers['#uv-chart'].legendCount ?? 0, 0);
const uvSpec = chartSpecs.at(-1);
assert.equal(uvSpec.data.datasets[0].borderColor, '#b26a00');
assert.equal((uvSpec.options.plugins.decorations.xRanges ?? []).length, 0);
assert.equal(uvSpec.options.plugins.decorations.yZones.length, 5);
assert.equal(uvSpec.options.plugins.decorations.dots[0].x,
    new Date('2026-10-08T17:00:00+02:00').getTime());
assert.equal(uvSpec.data.datasets[0].data[1].x,
    new Date('2026-10-08T12:00:00+02:00').getTime());
assert.equal(uvSpec.options.scales.x.min,
    new Date(solar.civil_twilight_begin).getTime());
assert.equal(uvSpec.options.scales.x.max,
    new Date(solar.civil_twilight_end).getTime());
assert.equal(uvSpec.options.scales.x.ticks.callback(
    new Date(solar.civil_twilight_begin).getTime()), '08:00');
const countBeforeSolarFailure = chartSpecs.length;
solarFailure = true;
savedSolar = null;
clearDataCache();
await renderUv(root);
assert.equal(chartSpecs.length, countBeforeSolarFailure);
assert.ok(containers['#uv-chart'].innerHTML.includes(strings.weather.no_data));
uvFile.data.hourly = [];
await renderUv(root);
assert.ok(root.innerHTML.includes(strings.weather.no_data));
assert.ok(!root.innerHTML.includes('class="card'));
"""
    result = subprocess.run(
        [node, "--experimental-default-type=module", "--input-type=module"],
        input=script,
        text=True,
        capture_output=True,
        cwd=WEB.parent,
        env={"TZ": "UTC"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
