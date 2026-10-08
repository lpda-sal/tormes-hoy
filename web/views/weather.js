import { renderChart, timeTicks } from "../charts.js";
import { loadData } from "../data.js";
import {
  age, dayLabel, esc, hourLabel, num, SOURCE_COLORS, statusBadge,
} from "../format.js";
import { t } from "../i18n.js";

const SOURCES = ["aemet", "openmeteo", "meteoblue"];
const HOUR = 3600000;

function seriesFor(forecasts, field, xs) {
  return SOURCES.map((key) => {
    const block = forecasts[key];
    const byTime = new Map(
      (block?.data?.hourly ?? []).map((h) => [new Date(h.time).getTime(), h[field] ?? null]),
    );
    return {
      label: block?.source?.label ?? key,
      color: SOURCE_COLORS[key],
      values: xs.map((x) => byTime.get(x) ?? null),
    };
  }).filter((s) => s.values.some((v) => v !== null));
}

function chartBlock(container, series, xs, unit, digits) {
  if (!series.length) {
    container.innerHTML = `<p class="muted">${t("weather.no_data")}</p>`;
    return;
  }
  renderChart(container, {
    x: xs,
    series,
    now: Date.now(),
    xTicks: timeTicks(xs[0], xs[xs.length - 1], 6 * HOUR),
    xFormat: (x) => hourLabel(x),
    titleFormat: (x) => `${dayLabel(x)} ${hourLabel(x)}`,
    valueFormat: (v) => `${num(v, digits)}${unit}`,
  });
}

function sourcesStatus(forecasts) {
  return SOURCES.map((key) => {
    const block = forecasts[key];
    const fetched = block?.fetched_at ? t("weather.fetched", { age: age(block.fetched_at) }) : "";
    return `<span><i style="background:${SOURCE_COLORS[key]}"></i>${esc(block?.source?.label ?? key)} ${statusBadge(block?.status)} <span class="muted">${fetched}</span></span>`;
  }).join("");
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
      return `<td><strong>${num(day.temperature_max)}°</strong>/${num(day.temperature_min)}°<br><span class="muted">${num(day.precipitation_probability)}%</span></td>`;
    }).join("");
    return `<tr><td>${dayLabel(date)}</td>${cells}</tr>`;
  }).join("");
  return `<div class="table-scroll"><table class="days"><thead><tr><th></th>${header}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function observationBlock(observation) {
  const data = observation?.data;
  if (!data) return `<p class="muted">${t("weather.no_data")} ${statusBadge(observation?.status ?? "error")}</p>`;
  return `
    <div class="row">
      <span class="big">${t("units.temperature", { v: num(data.temperature, 1) })}</span>
      <span>${t("home.humidity", { v: t("units.humidity", { v: num(data.humidity) }) })}</span>
      <span>${t("home.wind", { v: t("units.wind", { v: num(data.wind_speed) }) })}</span>
      <span>${t("weather.rain")}: ${t("units.rain", { v: num(data.precipitation, 1) })}</span>
    </div>
    <div class="muted">${t("home.observed_at", { station: esc(data.station_name ?? "AEMET"), age: age(data.time) })} ${statusBadge(observation.status)}</div>`;
}

export async function render(root) {
  const weather = await loadData("weather");
  const forecasts = weather.forecasts ?? {};
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: weather.location?.timezone,
    year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
  const xs = [...new Set(SOURCES.flatMap((key) =>
    (forecasts[key]?.data?.hourly ?? [])
      .filter((hour) => hour.time.slice(0, 10) === today)
      .map((hour) => new Date(hour.time).getTime()),
  ))].sort((left, right) => left - right);
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("weather.title")}</h1>
    <section class="card"><h2>${t("weather.observation")}</h2>${observationBlock(weather.observation)}</section>
    <div class="legend">${sourcesStatus(forecasts)}</div>
    <p class="chart-hint">${t("chart_hint")}</p>
    <section class="card"><h2>${t("weather.temperature_today")}</h2><div id="temp-chart"></div>
      <p class="muted">${t("weather.spread_note")}</p></section>
    <section class="card"><h2>${t("weather.rain_today")}</h2><div id="rain-chart"></div></section>
    <a class="next-days-link" href="#/weather/days">${t("home.next_days")}</a>`;
  chartBlock(root.querySelector("#temp-chart"), seriesFor(forecasts, "temperature", xs), xs, " °C", 1);
  chartBlock(root.querySelector("#rain-chart"), seriesFor(forecasts, "precipitation_probability", xs), xs, " %", 0);
}

export async function renderDays(root) {
  const weather = await loadData("weather");
  const forecasts = weather.forecasts ?? {};
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("weather.days_title")}</h1>
    <div class="legend">${sourcesStatus(forecasts)}</div>
    <section><h2>${t("weather.days_table")}</h2>${daysTable(forecasts)}</section>
    <a class="next-days-link" href="#/weather">${t("weather.title")}</a>`;
}
