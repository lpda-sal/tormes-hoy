import { renderChart, timeTicks } from "../charts.js";
import { loadData, loadSunTimes } from "../data.js";
import {
  age, civilNightRanges, dayLabel, esc, forecastTime, isNightHour, num, SOURCE_COLORS, statusBadge,
  wmoIcon, wmoText,
} from "../format.js";
import { t } from "../i18n.js";

const SOURCES = ["aemet", "openmeteo", "meteoblue"];
const HOUR = 3600000;
const OBSERVATION_COLOR = "#b26a00";
const AEMET_ICON_CODES = [
  ["clear", 0], ["few_clouds", 1], ["high_clouds", 2],
  ["cloud_intervals", 2], ["cloudy", 2], ["very_cloudy", 3],
  ["overcast", 3], ["fog", 45], ["mist", 45],
];
const METEOBLUE_ICON_CODES = new Map([
  [1, 0], [2, 1], [3, 2], [4, 3], [5, 45], [6, 61], [7, 80],
  [8, 95], [9, 71], [10, 85], [11, 71], [12, 61], [13, 71],
  [14, 61], [15, 71], [16, 61], [17, 71], [20, 3],
  [21, 95], [22, 95], [23, 95], [24, 95], [25, 95],
]);
// Meteoblue's hourly pictogram set differs from the daily one.
const METEOBLUE_HOURLY_ICON_CODES = new Map([
  [1, 0], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1], [7, 2], [8, 2], [9, 2],
  [10, 2], [11, 2], [12, 2], [13, 1], [14, 1], [15, 1], [16, 45], [17, 45],
  [18, 45], [19, 3], [20, 3], [21, 3], [22, 3], [23, 61], [24, 71], [25, 65],
  [26, 75], [27, 95], [28, 95], [29, 95], [30, 95], [31, 80], [32, 85],
  [33, 61], [34, 71], [35, 71],
]);

function forecastCondition(source, day, { hourly = false, night = false } = {}) {
  let code;
  let label;
  if (source === "aemet") {
    if (typeof day.sky !== "string") return null;
    const sky = day.sky.trim();
    const [clouds, ...precipitation] = sky.toLowerCase().split(t("aemet.with"));
    const cloud = AEMET_ICON_CODES.find(([key]) =>
      clouds === t(`aemet.sky.${key}`).toLowerCase());
    if (!cloud) return null;
    code = cloud[1];
    if (precipitation.length) {
      const condition = precipitation.join(t("aemet.with"));
      const weather = [["thunderstorm", 95], ["hail", 95], ["snow", 71], ["rain", 61]]
        .find(([key]) => condition.includes(t(`aemet.precipitation.${key}`)));
      if (!weather) return null;
      code = weather[1];
    }
    label = sky;
  } else if (source === "meteoblue") {
    const codes = hourly ? METEOBLUE_HOURLY_ICON_CODES : METEOBLUE_ICON_CODES;
    if (!codes.has(day.pictocode)) return null;
    code = codes.get(day.pictocode);
    label = t(`meteoblue.${hourly ? "hourly_pictocode" : "pictocode"}.${day.pictocode}`);
  } else {
    if (!Number.isFinite(day.weather_code)) return null;
    code = day.weather_code;
    label = wmoText(code);
  }
  const icon = wmoIcon(code, night);
  return icon === "·" ? null : { icon, label };
}

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

function hourlyConditions(forecasts, start, timeZone, solar) {
  const hours = Array.from({ length: 24 }, (_, index) => start + index * HOUR);
  const nights = hours.map((time) => isNightHour(time, solar, timeZone));
  const hourFormat = new Intl.DateTimeFormat("es-ES", {
    timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const dateFormat = new Intl.DateTimeFormat("es-ES", {
    timeZone, day: "numeric", month: "short", hour: "2-digit",
    minute: "2-digit", hourCycle: "h23",
  });
  const header = hours.map((time) => `<th scope="col" title="${esc(dateFormat.format(time))}">${hourFormat.format(time)}</th>`).join("");
  const rows = SOURCES.map((key) => {
    const block = forecasts[key];
    const byTime = new Map(
      (block?.status === "error" ? [] : block?.data?.hourly ?? []).map((row) => [
        forecastTime(row.time, timeZone), row,
      ]),
    );
    const cells = hours.map((time, index) => {
      const row = byTime.get(time);
      const condition = row
        ? forecastCondition(key, row, { hourly: true, night: nights[index] })
        : null;
      return condition
        ? `<td><span class="icon" role="img" aria-label="${esc(condition.label)}" title="${esc(condition.label)}">${condition.icon}</span></td>`
        : `<td aria-label="${t("weather.no_data")}"></td>`;
    }).join("");
    return `<tr><th scope="row" class="weather-hour-source" style="color:${SOURCE_COLORS[key]}">${esc(block?.source?.label ?? key)}</th>${cells}</tr>`;
  }).join("");
  return `<section class="card weather-hourly">
    <div class="table-scroll" tabindex="0" role="region" aria-label="${t("weather.hourly_conditions")}">
      <table class="weather-hours"><thead><tr><th scope="col" class="weather-hour-source" aria-label="${t("weather.sources")}"></th>${header}</tr></thead><tbody>${rows}</tbody></table>
    </div>
  </section>`;
}

function daysTable(forecasts, today) {
  const dates = [...new Set(SOURCES.flatMap((k) => (forecasts[k]?.data?.daily ?? []).map((d) => d.date)))]
    .filter((date) => typeof date === "string" && date >= today)
    .sort()
    .slice(0, 7);
  const header = SOURCES.map((k) => `<th>${esc(forecasts[k]?.source?.label ?? k)}</th>`).join("");
  const rows = dates.map((date) => {
    const cells = SOURCES.map((k) => {
      const day = (forecasts[k]?.data?.daily ?? []).find((d) => d.date === date);
      if (!day) return `<td class="muted">–</td>`;
      const weather = forecastCondition(k, day);
      const condition = weather
        ? `<div class="icon" role="img" aria-label="${esc(weather.label)}" title="${esc(weather.label)}">${weather.icon}</div>`
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
    ${hourlyConditions(forecasts, start, timeZone, solar)}
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
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: weather.location?.timezone,
    year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date()).map((part) => [part.type, part.value]));
  const today = `${parts.year}-${parts.month}-${parts.day}`;
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("weather.days_title")}</h1>
    ${daysTable(forecasts, today)}`;
}
