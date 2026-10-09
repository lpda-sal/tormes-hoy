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


def test_weather_chart_heights_are_scoped() -> None:
    styles = (WEB / "styles.css").read_text(encoding="utf-8")
    assert re.search(
        r"#temp-chart \.chart-canvas,\s*"
        r"#rain-chart \.chart-canvas\s*\{\s*height: 10rem;\s*\}",
        styles,
    )
    assert re.search(r"(?m)^\.chart-canvas\s*\{[^}]*height: 15rem;", styles)


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
import { render as renderRiver } from './web/views/river.js';
import { selectUvReading, SOURCE_COLORS, UV_COLORS } from './web/format.js';

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
    precipitation_probability: 5, weather_code: 0,
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
const riverFile = {source: {station: 'EA087'}, current: {status: 'ok',
    data: {time: '2026-10-08T11:00:00+02:00', flow_m3s: 6.8, level_m: 0.43}},
    readings: []};
const riverDaily = {daily: [
    {date: '2025-10-07', flow_m3s: {mean: 5}, level_m: {mean: 0.3}},
    {date: '2025-10-08', flow_m3s: {mean: 6}, level_m: {mean: 0.4}},
    {date: '2026-10-06', flow_m3s: {mean: 7}, level_m: {mean: 0.5}},
    {date: '2026-10-08', flow_m3s: {mean: 8}, level_m: {mean: 0.6}},
]};
const riverYearbook = {variables: {}};
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
    if (String(url).includes('river-observed-30d.json')) {
        return {ok: true, json: async () => riverFile};
    }
    if (String(url).includes('river-observed-daily.json')) {
        return {ok: true, json: async () => riverDaily};
    }
    if (String(url).includes('river-yearbook-stats.json')) {
        return {ok: true, json: async () => riverYearbook};
    }
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
    '#river-controls', '#river-unit', '#river-chart', '#river-notices',
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
assert.ok(root.innerHTML.includes('class="muted uv-at">A las 12:00'));
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
assert.ok(!root.innerHTML.includes('href="#/csck"'));
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
assert.ok(!root.innerHTML.includes('class="legend"'));
assert.ok(!root.innerHTML.includes(strings.weather.days_table));
assert.ok(!root.innerHTML.includes('href="#/weather"'));
assert.ok(root.innerHTML.includes('class="back" href="#/"'));
assert.ok(root.innerHTML.includes(`aria-label="${strings.wmo['0']}"`));
assert.ok(root.innerHTML.includes('☀️'));
assert.ok(root.innerHTML.includes('24°'));
assert.ok(root.innerHTML.includes('5%'));
weather.forecasts.openmeteo.data.daily[0].weather_code = null;
await renderDays(root);
assert.ok(!root.innerHTML.includes('role="img"'));
weather.forecasts.openmeteo.data.daily[0].weather_code = 999;
await renderDays(root);
assert.ok(!root.innerHTML.includes('role="img"'));
weather.forecasts.openmeteo.data.daily[0].weather_code = 0;
const iconForecasts = weather.forecasts;
const iconDay = iconForecasts.openmeteo.data.daily[0];
weather.forecasts = {...iconForecasts,
    aemet: {status: 'ok', data: {daily: [{...iconDay,
        sky: strings.aemet.sky.few_clouds}]}},
    meteoblue: {status: 'ok', data: {daily: [{...iconDay, pictocode: 2}]}},
};
const iconCells = () => {
    const row = root.innerHTML.match(
        /<tbody><tr><td>.*?<\/td>([\s\S]*?)<\/tr>/)[1];
    return [...row.matchAll(/<td>([\s\S]*?)<\/td>/g)].map(match => match[1]);
};
await renderDays(root);
assert.equal((root.innerHTML.match(/role="img"/g) ?? []).length, 3);
assert.ok(iconCells()[0].includes('🌤️'));
assert.ok(iconCells()[0].includes(
    `aria-label="${strings.aemet.sky.few_clouds}"`));
assert.ok(iconCells()[1].includes('☀️'));
assert.ok(iconCells()[2].includes('🌤️'));
assert.ok(iconCells()[2].includes(
    `aria-label="${strings.meteoblue.pictocode['2']}"`));
const aemetDay = weather.forecasts.aemet.data.daily[0];
for (const [sky, icon] of [
    [strings.aemet.sky.clear, '☀️'],
    [strings.aemet.sky.high_clouds, '⛅'],
    [strings.aemet.sky.cloud_intervals, '⛅'],
    [strings.aemet.sky.cloudy, '⛅'],
    [strings.aemet.sky.very_cloudy, '☁️'],
    [strings.aemet.sky.overcast, '☁️'],
    [strings.aemet.sky.fog, '🌫️'],
    [strings.aemet.sky.mist, '🌫️'],
    [strings.aemet.sky.cloudy + strings.aemet.with
        + strings.aemet.precipitation.rain, '🌧️'],
    [strings.aemet.sky.cloudy + strings.aemet.with
        + strings.aemet.precipitation.snow, '🌨️'],
    [strings.aemet.sky.cloudy + strings.aemet.with
        + strings.aemet.precipitation.thunderstorm, '⛈️'],
]) {
    aemetDay.sky = sky;
    await renderDays(root);
    assert.ok(iconCells()[0].includes(icon));
    assert.ok(iconCells()[0].includes(`aria-label="${sky}"`));
}
const meteoblueDay = weather.forecasts.meteoblue.data.daily[0];
for (const [pictocode, icon] of [
    [1, '☀️'], [3, '⛅'], [4, '☁️'], [5, '🌫️'], [6, '🌧️'],
    [7, '🌧️'], [8, '⛈️'], [9, '🌨️'], [10, '🌨️'], [11, '🌨️'],
    [12, '🌧️'], [13, '🌨️'], [14, '🌧️'], [15, '🌨️'],
    [16, '🌧️'], [17, '🌨️'], [20, '☁️'], [21, '⛈️'],
    [22, '⛈️'], [23, '⛈️'], [24, '⛈️'], [25, '⛈️'],
]) {
    meteoblueDay.pictocode = pictocode;
    await renderDays(root);
    assert.ok(iconCells()[2].includes(icon));
    assert.ok(iconCells()[2].includes(
        `aria-label="${strings.meteoblue.pictocode[pictocode]}"`));
}
for (const missing of [null, undefined, '', 'unknown']) {
    aemetDay.sky = missing;
    await renderDays(root);
    assert.ok(!iconCells()[0].includes('role="img"'));
}
for (const missing of [null, undefined, 0, 18, 19, 999, 1.5, '1']) {
    meteoblueDay.pictocode = missing;
    await renderDays(root);
    assert.ok(!iconCells()[2].includes('role="img"'));
}
delete meteoblueDay.pictocode;
await renderDays(root);
assert.ok(!iconCells()[2].includes('role="img"'));
aemetDay.sky = strings.aemet.sky.cloudy + strings.aemet.with
    + strings.aemet.precipitation.rain + ' <svg onload="alert(1)">';
await renderDays(root);
assert.ok(iconCells()[0].includes('&lt;svg onload=&quot;'));
assert.ok(!root.innerHTML.includes('<svg'));
weather.forecasts = iconForecasts;
const originalDailyForecasts = weather.forecasts;
const originalDaysClock = now;
const originalDaysLocation = weather.location;
weather.location = {...summary.location};
const dailyRows = Array.from({length: 10}, (_, index) => ({
    date: `2026-10-${String(index + 7).padStart(2, '0')}`,
    temperature_max: 24, temperature_min: 12,
    precipitation_probability: 5, weather_code: 0,
}));
weather.forecasts = Object.fromEntries(
    ['aemet', 'openmeteo', 'meteoblue'].map((key, index) => [key, {
        status: 'ok', source: {label: key},
        data: {daily: dailyRows.slice(index)},
    }]));
for (const [clock, firstDate, lastDate] of [
    ['2026-10-08T23:50:00+02:00', '2026-10-08', '2026-10-14'],
    ['2026-10-09T00:10:00+02:00', '2026-10-09', '2026-10-15'],
]) {
    now = new NativeDate(clock);
    await renderDays(root);
    const {dayLabel} = await import('./web/format.js');
    const body = root.innerHTML.match(/<tbody>([\s\S]*?)<\/tbody>/)[1];
    const labels = [...body.matchAll(/<tr><td>(.*?)<\/td>/g)]
        .map(match => match[1]);
    assert.equal(labels.length, 7);
    assert.equal(labels[0], dayLabel(firstDate));
    assert.equal(labels.at(-1), dayLabel(lastDate));
    assert.ok(!labels.includes(dayLabel('2026-10-07')));
    if (firstDate === '2026-10-09') {
        assert.ok(!labels.includes(dayLabel('2026-10-08')));
    }
}
now = new NativeDate('2026-10-20T12:00:00+02:00');
await renderDays(root);
assert.ok(!root.innerHTML.includes('<tr><td>'));
weather.forecasts = originalDailyForecasts;
weather.location = originalDaysLocation;
now = originalDaysClock;
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
                    humidity: 60, precipitation_probability: 75,
                    sky: strings.aemet.sky.clear,
                    weather_code: 3, pictocode: 2};
            })}};
}
weather.forecasts.aemet.data.hourly[1].sky = null;
weather.forecasts.openmeteo.data.hourly[1].weather_code = 999;
weather.forecasts.meteoblue.data.hourly[1].pictocode = null;
await renderWeather(root);
assert.ok(root.innerHTML.includes('<h1>Tiempo</h1>'));
assert.deepEqual([...root.innerHTML.matchAll(/<h2>([^<]+)<\/h2>/g)]
    .map(match => match[1]), ['Temperatura', 'Lluvia']);
const hourlyPanel = () => root.innerHTML.match(
    /<section class="card weather-hourly">([\s\S]*?)<\/section>/)[1];
const hourlyHeaders = () => [...hourlyPanel().matchAll(
    /<th scope="col" title="[^"]*">([^<]*)<\/th>/g)]
    .map(match => match[1]);
const hourlyRows = () => [...hourlyPanel().matchAll(
    /<tr><th scope="row"[\s\S]*?<\/th>([\s\S]*?)<\/tr>/g)]
    .map(match => [...match[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)]
        .map(cell => cell[1]));
assert.deepEqual(hourlyHeaders(), Array.from({length: 24}, (_, index) =>
    `${String((10 + index) % 24).padStart(2, '0')}:00`));
assert.equal(hourlyRows().length, 3);
assert.ok(hourlyRows().every(row => row.length === 24 && row[1] === ''));
assert.ok(hourlyRows()[0][0].includes('☀️'));
assert.ok(hourlyRows()[1][0].includes('☁️'));
assert.ok(hourlyRows()[2][0].includes('🌤️'));
assert.ok(!hourlyPanel().includes('°'));
assert.ok(!hourlyPanel().includes('%'));
assert.ok(!hourlyPanel().includes(strings.home.humidity.split('{v}')[0]));
assert.ok(hourlyPanel().includes('tabindex="0"'));
assert.ok(!hourlyPanel().includes('<h2>'));
assert.ok(hourlyPanel().includes(
    `aria-label="${strings.weather.hourly_conditions}"`));
assert.ok(root.innerHTML.indexOf('id="rain-chart"')
    < root.innerHTML.indexOf('class="card weather-hourly"'));
assert.ok(root.innerHTML.indexOf('class="card weather-hourly"')
    < root.innerHTML.indexOf('class="weather-sources"'));
weather.forecasts.meteoblue.status = 'error';
await renderWeather(root);
assert.ok(hourlyRows()[2].every(cell => cell === ''));
assert.ok(hourlyRows()[0][0].includes('☀️'));
weather.forecasts.meteoblue.status = 'stale';
await renderWeather(root);
assert.ok(hourlyRows()[2][0].includes('🌤️'));
weather.forecasts.meteoblue.status = 'ok';
await renderWeather(root);
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
        precipitation_probability: 30, weather_code: 3,
        sky: strings.aemet.sky.overcast, pictocode: 4}));
}
await renderWeather(root);
const lateCharts = chartSpecs.slice(-2);
assert.equal(hourlyHeaders()[0], '23:00');
assert.equal(hourlyHeaders().at(-1), '22:00');
assert.equal(hourlyHeaders().length, 24);
assert.ok(hourlyRows().every(row => row[0].includes('☁️')
    && row[1].includes('☁️') && row[2] === '' && row[23].includes('☁️')));
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
assert.equal(hourlyHeaders()[0], '00:00');
assert.equal(hourlyHeaders().at(-1), '23:00');
assert.ok(hourlyRows().every(row => row[0].includes('☁️')
    && row[1] === '' && row[22].includes('☁️') && row[23].includes('☁️')));
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
assert.ok(hourlyRows().every(row => row.every(cell => cell === '')));
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
assert.ok(root.innerHTML.includes('A las 12:00'));
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
    new Date('2026-10-08T12:00:00+02:00').getTime());
assert.equal(uvSpec.options.plugins.decorations.dots[0].y, 5);
assert.equal(uvSpec.data.datasets[0].data[1].x,
    new Date('2026-10-08T12:00:00+02:00').getTime());
assert.equal(uvSpec.options.scales.x.min,
    new Date(solar.civil_twilight_begin).getTime());
assert.equal(uvSpec.options.scales.x.max,
    new Date(solar.civil_twilight_end).getTime());
assert.equal(uvSpec.options.scales.x.ticks.callback(
    new Date(solar.civil_twilight_begin).getTime()), '08:00');
const originalFetch = globalThis.fetch;
const originalUvHourly = uvFile.data.hourly;
const originalSummaryUv = summary.uv;
const originalUvMax = uvFile.data.max;
summary.uv = {status: 'ok', data: {
    now: 3, max: 11, max_time: '14:00', protection: null,
}};
uvFile.data.max = 11;
const nearbyUv = [
    {time: '2026-10-08T11:00', uv: 9},
    {time: '2026-10-08T12:00', uv: 2},
    {time: '2026-10-08T13:00', uv: 6},
    {time: '2026-10-08T14:00', uv: 11},
];
uvFile.data.hourly = nearbyUv;
for (const [clock, value, hour] of [
    ['12:10', 6, '13:00'], ['12:50', 6, '13:00'], ['11:40', 9, '11:00'],
]) {
    now = new NativeDate(`2026-10-08T${clock}:00+02:00`);
    const expectedTime = new NativeDate(`2026-10-08T${hour}:00+02:00`)
        .getTime();
    assert.deepEqual(selectUvReading(nearbyUv, 'Europe/Madrid'),
        {value, time: expectedTime});
    await render(root);
    assert.ok(root.innerHTML.includes(`A las ${hour}`), root.innerHTML);
    assert.ok(root.innerHTML.includes(`>${value},0</span>`));
    const homeDecorations = chartSpecs.at(-1).options.plugins.decorations;
    assert.equal(homeDecorations.now, now.getTime());
    assert.equal(homeDecorations.dots[0].x, expectedTime);
    assert.equal(homeDecorations.dots[0].y, value);
    await renderUv(root);
    assert.ok(root.innerHTML.includes(`A las ${hour}`));
    assert.ok(root.innerHTML.includes(`>${value},0</span>`));
    assert.equal(chartSpecs.at(-1).options.plugins.decorations.now,
        homeDecorations.now);
    assert.deepEqual(chartSpecs.at(-1).options.plugins.decorations.dots,
        homeDecorations.dots);
    assert.equal(chartSpecs.at(-1).options.plugins.decorations.dots[0].x,
        expectedTime);
    assert.equal(chartSpecs.at(-1).options.plugins.decorations.dots[0].y,
        value);
}
const tieRows = nearbyUv.slice(1, 3).map(row => ({...row, uv: 0}));
const stamp = time => new NativeDate(time).getTime();
assert.deepEqual(selectUvReading(nearbyUv, 'Europe/Madrid',
    stamp('2026-10-08T12:00:00+02:00')),
    {value: 6, time: stamp('2026-10-08T13:00:00+02:00')});
assert.equal(selectUvReading([], 'Europe/Madrid'), null);
assert.equal(selectUvReading(tieRows, 'Europe/Madrid',
    stamp('2026-10-08T12:30:00+02:00')).time,
    stamp('2026-10-08T13:00:00+02:00'));
assert.equal(selectUvReading(tieRows, 'Europe/Madrid',
    stamp('2026-10-08T12:10:00+02:00')).time,
    stamp('2026-10-08T12:00:00+02:00'));
const midnightRows = [
    {time: '2026-10-08T23:00', uv: 1},
    {time: '2026-10-09T00:00', uv: 0},
    {time: '2026-10-09T01:00', uv: 5},
];
assert.deepEqual(selectUvReading(midnightRows, 'Europe/Madrid',
    stamp('2026-10-08T23:50:00+02:00')),
    {value: 1, time: stamp('2026-10-08T23:00:00+02:00')});
assert.equal(selectUvReading([
    {time: 'invalid', uv: 10}, {time: '2026-10-08T12:00', uv: null},
], 'Europe/Madrid'), null);
assert.deepEqual(selectUvReading([
    {time: '2026-10-08T13:00+02:00', uv: 0},
], 'Europe/Madrid'),
    {value: 0, time: stamp('2026-10-08T13:00:00+02:00')});
uvFile.data.hourly = originalUvHourly;
uvFile.data.max = originalUvMax;
summary.uv = originalSummaryUv;
globalThis.fetch = async (url) => {
    if (String(url).includes('api.sunrise-sunset.org')
        && new URL(url).searchParams.get('date') === '2026-10-09') {
        const nextSolar = Object.fromEntries(Object.entries(solar).map(
            ([key, value]) => [key, key === 'date' ? '2026-10-09'
                : new NativeDate(new NativeDate(value).getTime()
                    + 86400000).toISOString()]));
        return {ok: true, json: async () => nextSolar};
    }
    return originalFetch(url);
};
now = new NativeDate('2026-10-09T00:30:00+02:00');
await render(root);
const midnightUv = chartSpecs.at(-1);
assert.equal(midnightUv.data.datasets[0].borderColor, '#b26a00');
assert.equal(midnightUv.options.scales.x.min,
    new NativeDate(solar.civil_twilight_begin).getTime());
assert.equal(midnightUv.options.scales.x.max,
    new NativeDate(solar.civil_twilight_end).getTime());
assert.ok(midnightUv.data.datasets[0].data.some(point =>
    point.x >= midnightUv.options.scales.x.min
    && point.x <= midnightUv.options.scales.x.max));
globalThis.fetch = originalFetch;
now = new NativeDate('2026-10-08T12:00:00+02:00');
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
let riverControls;
containers['#river-controls'].addEventListener = (_, handler) => {
    riverControls = handler;
};
summary.river.data = {...riverFile.current.data};
assert.equal(strings.river.last_month, 'Últimos meses');
assert.equal(strings.river.by_year, 'Últimos años');
for (const [status, color] of [
    ['safe', UV_COLORS.low], ['caution', UV_COLORS.moderate],
    ['danger', UV_COLORS.very_high],
]) {
    summary.river.flow_status = status;
    await renderRiver(root);
    assert.ok(root.innerHTML.includes('<h1>Río Tormes '));
    assert.ok(!root.innerHTML.includes('EA087'));
    assert.ok(root.innerHTML.includes(`class="flow-chip ${status}"`));
    assert.ok(root.innerHTML.includes(`background:${color};color:#111`));
    assert.ok(root.innerHTML.includes(strings.river.flow_status[status]));
    assert.ok(root.innerHTML.includes('6,80 m³/s</span>'));
    assert.ok(root.innerHTML.includes('class="level-chip">0,43 m</span>'));
    assert.ok(!root.innerHTML.includes('Lectura hace'));
    assert.ok(root.innerHTML.indexOf(strings.chart_hint)
        < root.innerHTML.indexOf('<section class="card">'));
    assert.ok(!root.innerHTML.includes(strings.river.source_note));
    for (const text of ['id="river-notices"',
        strings.river.source, strings.river.flow_status_note]) {
        assert.ok(root.innerHTML.indexOf(text)
            > root.innerHTML.indexOf('</section>'));
    }
    assert.ok(root.innerHTML.indexOf(strings.river.source)
        < root.innerHTML.indexOf(strings.river.flow_status_note));
    assert.ok(root.innerHTML.indexOf('class="river-current"')
        < root.innerHTML.indexOf('<section class="card">'));
}
assert.equal(chartSpecs.at(-1).data.datasets[0].label, '2025');
assert.equal(chartSpecs.at(-1).data.datasets[0].borderColor, '#1f5f8b');
assert.equal(chartSpecs.at(-1).data.datasets[1].label, '2026');
assert.equal(chartSpecs.at(-1).data.datasets[1].borderColor, '#e07a1f');
assert.ok(containers['#river-controls'].innerHTML.includes(
    'data-range="month" aria-pressed="true"'));
const defaultRiverPoints = chartSpecs.at(-1).data.datasets[1].data;
assert.equal(chartSpecs.at(-1).options.scales.y.min, undefined);
assert.equal(chartSpecs.at(-1).options.scales.y.max, undefined);
assert.equal(defaultRiverPoints.length, 62);
assert.equal(defaultRiverPoints[0].x,
    new NativeDate('2026-08-08T12:00:00Z').getTime());
assert.equal(defaultRiverPoints.at(-1).x,
    new NativeDate('2026-10-08T12:00:00Z').getTime());
riverControls({target: {closest: () => ({dataset: {range: 'year'}})}});
assert.equal(chartSpecs.at(-1).data.datasets[1].data.length, 366);
assert.equal(chartSpecs.at(-1).options.scales.y.min, 0);
assert.equal(chartSpecs.at(-1).options.scales.y.max, 250);
assert.ok(containers['#river-controls'].innerHTML.includes(
    'data-range="year" aria-pressed="true"'));
riverControls({target: {closest: () => ({dataset: {variable: 'level_m'}})}});
assert.ok(containers['#river-unit'].textContent.includes(strings.river.level));
assert.equal(chartSpecs.at(-1).options.plugins.decorations.dots[0].y, 0.43);
assert.equal(chartSpecs.at(-1).options.scales.y.min, undefined);
assert.equal(chartSpecs.at(-1).options.scales.y.max, undefined);
assert.equal(chartSpecs.at(-1).options.scales.y.ticks.callback(0.333333),
    '0,33');
assert.equal(chartSpecs.at(-1).options.scales.y.ticks.callback(1), '1,00');
riverControls({target: {closest: () => ({dataset: {range: 'month'}})}});
assert.equal(chartSpecs.at(-1).options.scales.y.ticks.callback(1.234567),
    '1,23');
const monthLevel = chartSpecs.at(-1).data.datasets;
assert.deepEqual(monthLevel.map(series => series.label), ['2025', '2026']);
assert.deepEqual(monthLevel[0].data.slice(-3).map(point => point.y),
    [null, 0.3, 0.4]);
assert.deepEqual(monthLevel[1].data.slice(-3).map(point => point.y),
    [0.5, null, null]);
assert.equal(monthLevel[0].data.at(-1).x, monthLevel[1].data.at(-1).x);
riverControls({target: {closest: () => ({dataset: {variable: 'flow_m3s'}})}});
const monthFlow = chartSpecs.at(-1).data.datasets;
assert.deepEqual(monthFlow[0].data.slice(-3).map(point => point.y),
    [null, 5, 6]);
assert.deepEqual(monthFlow[1].data.slice(-3).map(point => point.y),
    [7, null, null]);
assert.equal(monthFlow[0].borderColor, '#1f5f8b');
assert.equal(monthFlow[1].borderColor, '#e07a1f');
assert.equal(monthFlow[1].spanGaps, 86400000);
const originalRiverDays = riverDaily.daily;
riverDaily.daily = [...originalRiverDays,
    {date: '2026-10-07', flow_m3s: {mean: 9}, level_m: {mean: 0.7}},
    {date: '2026-10-09', flow_m3s: {mean: 10}, level_m: {mean: 0.8}},
];
for (const range of ['month', 'year']) {
    for (const [variable, mean, reading, previous] of [
        ['flow_m3s', 9, 6.8, 6], ['level_m', 0.7, 0.43, 0.4],
    ]) {
        riverControls({target: {closest: () => ({dataset: {range}})}});
        riverControls({target: {closest: () => ({dataset: {variable}})}});
        const spec = chartSpecs.at(-1);
        const current = spec.data.datasets[1].data;
        const yesterday = range === 'month'
            ? new NativeDate('2026-10-07T12:00:00Z').getTime()
            : (Date.UTC(2000, 9, 7) - Date.UTC(2000, 0, 1)) / 86400000;
        const today = yesterday + (range === 'month' ? 86400000 : 1);
        assert.equal(current.find(point => point.x === yesterday).y, mean);
        assert.ok(current.filter(point => point.x >= today)
            .every(point => point.y === null));
        assert.equal(spec.data.datasets[0].data.find(
            point => point.x === today).y, previous);
        const dot = spec.options.plugins.decorations.dots[0];
        assert.equal(dot.y, reading);
        assert.ok(dot.x > yesterday);
        if (range === 'month') assert.equal(dot.x,
            new NativeDate(riverFile.current.data.time).getTime());
    }
}
riverDaily.daily = originalRiverDays;
riverControls({target: {closest: () => ({dataset: {variable: 'flow_m3s'}})}});
riverDaily.daily = riverDaily.daily.filter(day => day.date.startsWith('2026'));
riverControls({target: {closest: () => ({dataset: {range: 'month'}})}});
assert.ok(chartSpecs.at(-1).data.datasets[0].data.every(
    point => point.y === null));
assert.ok(!containers['#river-notices'].innerHTML.includes(
    strings.river.no_year_history.replace('{year}', '2025')));
riverDaily.daily = riverDaily.daily.filter(day => day.date === '2026-10-06');
riverControls({target: {closest: () => ({dataset: {range: 'month'}})}});
assert.equal(chartSpecs.at(-1).data.datasets[1].pointRadius, 3);
riverDaily.daily.push(
    {date: '2023-03-01', flow_m3s: {mean: 9}},
    {date: '2024-02-29', flow_m3s: {mean: 10}},
);
now = new NativeDate('2024-03-01T12:00:00Z');
riverControls({target: {closest: () => ({dataset: {range: 'month'}})}});
const leapMonth = chartSpecs.at(-1).data.datasets;
assert.equal(leapMonth[0].data.at(-2).y, null);
assert.equal(leapMonth[0].data.at(-1).y, 9);
assert.equal(leapMonth[1].data.at(-2).y, 10);
for (const [clock, startDate] of [
    ['2026-01-15', '2025-11-15'],
    ['2026-04-30', '2026-02-28'],
    ['2024-04-30', '2024-02-29'],
]) {
    now = new NativeDate(`${clock}T12:00:00Z`);
    riverControls({target: {closest: () => ({dataset: {range: 'month'}})}});
    const points = chartSpecs.at(-1).data.datasets[1].data;
    assert.equal(points[0].x,
        new NativeDate(`${startDate}T12:00:00Z`).getTime());
    assert.equal(points.at(-1).x, now.getTime());
    assert.ok(points.every((point, index) => index === 0
        || point.x - points[index - 1].x === 86400000));
}
now = new NativeDate('2026-10-08T12:00:00+02:00');
const bookStats = Array.from({length: 366}, (_, index) => ({
    md: new NativeDate(Date.UTC(2000, 0, index + 1))
        .toISOString().slice(5, 10),
    min: 1, p25: 3, p50: 5, p75: 7, max: 9,
}));
riverYearbook.variables.flow_m3s = {period: '2012-2021', stats: bookStats};
riverYearbook.variables.level_m = {period: '2018-2021', stats: bookStats};
for (const range of ['year', 'month']) {
    riverControls({target: {closest: () => ({dataset: {range}})}});
    const bandSpec = chartSpecs.at(-1);
    const datasets = bandSpec.data.datasets;
    assert.equal(datasets[1].label, 'Mínimo y máximo 2012-2021');
    assert.equal(datasets[1].data[0].y, 9);
    assert.equal(datasets[0].data[0].y, 1);
    assert.equal(datasets[3].label, 'Cuartiles 25–75 % 2012-2021');
    assert.equal(datasets[3].data[0].y, 7);
    assert.equal(datasets[2].data[0].y, 3);
    assert.ok(datasets[1].order > datasets[3].order);
    assert.ok(datasets[3].order > datasets[4].order);
    assert.equal(datasets[1].fill, '-1');
    assert.equal(datasets[3].fill, '-1');
    const tooltip = bandSpec.options.plugins.tooltip.callbacks;
    for (const [index, lower, upper] of [[1, 1, 9], [3, 3, 7]]) {
        const item = {dataset: datasets[index], dataIndex: 0,
            raw: datasets[index].data[0], chart: {data: {datasets}}};
        assert.ok(tooltip.label(item).endsWith(
            `${lower},00 m³/s – ${upper},00 m³/s`));
        assert.equal(tooltip.labelColor(item).backgroundColor,
            datasets[index].bandColor);
    }
    assert.ok(!containers['#river-notices'].innerHTML.includes('lecturas'));
}
riverControls({target: {closest: () => ({dataset: {variable: 'level_m'}})}});
assert.equal(chartSpecs.at(-1).data.datasets[1].label,
    'Mínimo y máximo 2018-2021');
riverYearbook.variables.level_m.stats = bookStats.map(
    ({min, max, ...row}) => row);
riverControls({target: {closest: () => ({dataset: {variable: 'level_m'}})}});
assert.equal(chartSpecs.at(-1).data.datasets[1].label,
    'Cuartiles 25–75 % 2018-2021');
assert.ok(!chartSpecs.at(-1).data.datasets.some(
    dataset => dataset.label.startsWith('Mínimo y máximo')));
summary.river.data.time = '2026-10-08T10:00:00+02:00';
await renderRiver(root);
assert.ok(root.innerHTML.includes('class="flow-chip unknown"'));
assert.ok(!root.innerHTML.includes('class="muted flow-status"'));
summary.river.data = {...riverFile.current.data};
summary.river.flow_status = null;
await renderRiver(root);
assert.ok(root.innerHTML.includes('class="flow-chip unknown"'));
riverFile.current = {status: 'error', data: null};
await renderRiver(root);
assert.ok(root.innerHTML.includes(strings.weather.no_data));
assert.ok(!root.innerHTML.includes('class="river-current"'));
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
