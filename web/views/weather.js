import { renderChart, timeTicks } from "../charts.js";
import { loadData, loadSunTimes } from "../data.js";
import {
  age, civilNightRanges, dayLabel, esc, forecastTime, num, SOURCE_COLORS, statusBadge,
  wmoIcon, wmoText,
} from "../format.js";
import { t } from "../i18n.js";

const SOURCES = ["aemet", "openmeteo", "meteoblue"];
const HOUR = 3600000;
const OBSERVATION_COLOR = "#b26a00";

function seriesFor(forecasts, field, xs, timeZone) {
  return SOURCES.map((key) => {
    const block = forecasts[key];
    const byTime = new Map(
      (block?.status === "error" ? [] : block?.data?.hourly ?? []).map((h) => [
        forecastTime(h.time, timeZone), Number.isFinite(h[field]) ? h[field] : null,
      ]),
    );
    return {
      label: block?.source?.label ?? key,
      color: SOURCE_COLORS[key],
      values: xs.map((x) => byTime.get(x) ?? null),
      spanGaps: HOUR,
    };
  }).filter((s) => s.values.some((v) => v !== null));
}

function chartBlock(container, series, xs, unit, digits, timeZone, bounds = {}) {
  if (!series.length) {
    container.innerHTML = `<p class="muted">${t("weather.no_data")}</p>`;
    return;
  }
  renderChart(container, {
    x: xs,
    series,
    showLegend: false,
    now: Date.now(),
    xMin: xs.length === 1 ? xs[0] - HOUR / 2 : xs[0],
    xMax: xs.length === 1 ? xs[0] + HOUR / 2 : xs[xs.length - 1],
    xTicks: timeTicks(xs[0], xs[xs.length - 1], 6 * HOUR),
    xFormat: (x) => new Intl.DateTimeFormat("es-ES", {
      timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).format(new Date(x)),
    titleFormat: (x) => new Intl.DateTimeFormat("es-ES", {
      timeZone, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
    }).format(new Date(x)),
    valueFormat: (v) => `${num(v, digits)}${unit}`,
    yFormat: (v) => `${num(v)}${unit}`,
    ...bounds,
  });
}

function sourcesStatus(forecasts, observation) {
  const sources = SOURCES.map((key) => {
    const block = forecasts[key];
    const fetched = block?.fetched_at ? t("weather.fetched", { age: age(block.fetched_at) }) : "";
    return `<span><i style="background:${SOURCE_COLORS[key]}"></i>${esc(block?.source?.label ?? key)} ${statusBadge(block?.status)} <span class="muted">${fetched ? `(${fetched})` : ""}</span></span>`;
  }).join("");
  if (!observation) return sources;
  const reading = observation.data?.time
    ? t("home.river_reading", { age: age(observation.data.time) }) : "";
  return `<span><i class="dot" style="background:${OBSERVATION_COLOR}"></i>${esc(observationLabel(observation))} ${statusBadge(observation.status)} <span class="muted">${reading ? `(${reading})` : ""}</span></span>${sources}`;
}

function observationLabel(observation) {
  return observation?.source?.label
    ? t("weather.observation_source", { source: observation.source.label })
    : t("weather.observation");
}

function daysTable(forecasts) {
  const dates = [...new Set(SOURCES.flatMap((k) => (forecasts[k]?.data?.daily ?? []).map((d) => d.date)))]
    .sort()
    .slice(0, 7);
  const header = SOURCES.map((k) => `<th>${esc(forecasts[k]?.source?.label ?? k)}</th>`).join("");
  const rows = dates.map((date) => {
    const cells = SOURCES.map((k) => {
      const day = (forecasts[k]?.data?.daily ?? []).find((d) => d.date === date);
      if (!day) return `<td class="muted">–</td>`;
      const icon = Number.isFinite(day.weather_code) ? wmoIcon(day.weather_code) : "";
      const condition = icon && icon !== "·"
        ? `<div class="icon" role="img" aria-label="${esc(wmoText(day.weather_code))}" title="${esc(wmoText(day.weather_code))}">${icon}</div>`
        : "";
      return `<td>${condition}<strong>${num(day.temperature_max)}°</strong>/${num(day.temperature_min)}°<br><span class="muted">${num(day.precipitation_probability)}%</span></td>`;
    }).join("");
    return `<tr><td>${dayLabel(date)}</td>${cells}</tr>`;
  }).join("");
  return `<div class="table-scroll"><table class="days"><thead><tr><th></th>${header}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

export async function render(root) {
  const weather = await loadData("weather");
  const forecasts = weather.forecasts ?? {};
  const timeZone = weather.location?.timezone;
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: weather.location?.timezone,
    year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
  const hour = new Intl.DateTimeFormat("en-GB", {
    timeZone, hour: "2-digit", hourCycle: "h23",
  }).format(new Date());
  const start = forecastTime(`${today}T${hour}:00`, timeZone);
  const end = start + 24 * HOUR;
  const solar = await loadSunTimes(weather.location, today).catch(() => null);
  const observation = weather.observation;
  const observedTime = observation?.status !== "error" && observation?.data?.time
    ? forecastTime(observation.data.time, timeZone) : NaN;
  const xs = [...new Set([...SOURCES.flatMap((key) =>
    (forecasts[key]?.status === "error" ? [] : forecasts[key]?.data?.hourly ?? [])
      .map((hour) => forecastTime(hour.time, timeZone))
      .filter((time) => time >= start && time < end),
  ), ...(Number.isFinite(observedTime) ? [observedTime] : [])])]
    .sort((left, right) => left - right);
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("weather.title")}</h1>
    <p class="muted">${t("weather.spread_note")}</p>
    <p class="chart-hint">${t("chart_hint")}</p>
    <section class="card"><h2>${t("weather.temperature_today")}</h2><div id="temp-chart"></div></section>
    <section class="card"><h2>${t("weather.rain_today")}</h2><div id="rain-chart"></div></section>
    <div class="weather-sources">
      <p class="weather-sources-label">${t("weather.sources")}</p>
      <div class="legend">${sourcesStatus(forecasts, observation)}</div>
    </div>`;
  const night = civilNightRanges(xs, solar, timeZone);
  for (const [selector, field, unit, digits, bounds] of [
    ["#temp-chart", "temperature", " °C", 1, {}],
    ["#rain-chart", "precipitation_probability", " %", 0, { yMin: 0, yMax: 100 }],
  ]) {
    const series = seriesFor(forecasts, field, xs, timeZone);
    if (Number.isFinite(observedTime) && Number.isFinite(observation.data[field])) {
      series.push({
        label: observationLabel(observation), color: OBSERVATION_COLOR,
        values: xs.map((x) => x === observedTime ? observation.data[field] : null),
        showLine: false, pointRadius: 5, order: -1,
      });
    }
    chartBlock(root.querySelector(selector), series, xs, unit, digits, timeZone, {
      ...bounds, xRanges: night,
    });
  }
}

export async function renderDays(root) {
  const weather = await loadData("weather");
  const forecasts = weather.forecasts ?? {};
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("weather.days_title")}</h1>
    ${daysTable(forecasts)}`;
}
