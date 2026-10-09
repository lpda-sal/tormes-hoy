import { loadData, loadSunTimes } from "../data.js";
import { renderChart } from "../charts.js";
import {
  age, civilNightRanges, esc, forecastTime, hourLabel, num, selectUvReading, statusBadge, uvChip, uvLevel, wmoIcon, wmoText,
  SOURCE_COLORS, UV_COLORS, UV_ZONES,
} from "../format.js";
import { t } from "../i18n.js";

function weatherNowCard(summary) {
  const obs = summary.weather_now;
  const model = summary.weather_now_model;
  const useObs = obs?.data && obs.status !== "error";
  const data = useObs ? obs.data : model?.data;
  const status = useObs ? obs.status : model?.status;
  if (!data) {
    return `<a class="card" href="#/weather"><h2>${t("home.weather_now")}${statusBadge("error")}</h2></a>`;
  }
  const icon = useObs ? "" : wmoIcon(data.weather_code);
  const caption = useObs
    ? t("home.river_reading", { age: age(data.time) })
    : t("home.model_reading", { age: age(data.time) });
  return `
    <a class="card" href="#/weather">
      <h2>${t("home.weather_now")}${statusBadge(status)}</h2>
      <div class="big">${icon} ${t("units.temperature", { v: num(data.temperature, 1) })}</div>
      ${useObs ? "" : `<div>${esc(wmoText(data.weather_code))}</div>`}
      ${data.apparent_temperature !== undefined && data.apparent_temperature !== null
        ? `<div class="muted">${t("home.feels_like", { v: t("units.temperature", { v: num(data.apparent_temperature) }) })}</div>` : ""}
      <div class="muted weather-details">
        <div>${t("home.humidity", { v: t("units.humidity", { v: num(data.humidity) }) })}</div>
        <div class="muted weather-rain">${t("home.rain_amount", { v: t("units.rain", { v: num(data.precipitation, 1) }) })}</div>
        <div>${t("home.wind", { v: t("units.wind", { v: num(data.wind_speed) }) })}</div>
        <div>${t("home.wind_gust", { v: t("units.wind", { v: num(data.wind_gust) }) })}</div>
      </div>
      <div class="muted weather-reading">${caption}</div>
    </a>`;
}

function upcomingHours(summary, block) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: summary.location.timezone, year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date()).map((part) => [part.type, part.value]));
  const date = `${parts.year}-${parts.month}-${parts.day}`;
  const start = forecastTime(`${date}T${parts.hour}:00`, summary.location.timezone);
  const end = start + 24 * 3600000;
  return (block?.data ?? []).filter((row) => {
    if (!Number.isFinite(new Date(row.time).getTime())) return false;
    const time = forecastTime(row.time, summary.location.timezone);
    return time >= start && time < end;
  }).sort((left, right) => forecastTime(left.time, summary.location.timezone)
    - forecastTime(right.time, summary.location.timezone));
}

function restOfDayCard(block, hours) {
  const content = block?.status === "error" && !hours.length
    ? ""
    : hours.length
    ? `<div class="hours">${hours.map((h) => `
        <div class="hour">
          <div class="muted">${hourLabel(h.time)}</div>
          <div class="icon" title="${esc(wmoText(h.weather_code))}">${wmoIcon(h.weather_code)}</div>
          <div>${num(h.temperature)}°</div>
          <div class="muted">${num(h.precipitation_probability)}%</div>
        </div>`).join("")}</div>`
    : `<p class="muted">${t("home.no_more_hours")}</p>`;
  return `
    <a class="card wide hours-card" href="#/weather">
      <h2>${t("home.rest_of_day")}${statusBadge(block?.status)}</h2>
      ${content}
    </a>`;
}

function uvCard(summary, uvFile) {
  const block = summary.uv;
  const uv = block?.data ?? {};
  const protection = uv.protection
    ? `${t("uv.protection_label")}<br>${t("uv.protection_hours", { from: uv.protection.from, to: uv.protection.to })}`
    : t("uv.protection_none");
  const reading = selectUvReading(uvFile?.data?.hourly, summary.location.timezone);
  const level = uvLevel(reading?.value);
  const time = reading ? new Intl.DateTimeFormat("es-ES", {
    timeZone: summary.location.timezone, hour: "2-digit", minute: "2-digit",
    hourCycle: "h23",
  }).format(reading.time) : "";
  return `
    <section class="card wide uv-card">
      <a class="uv-summary" href="#/uv">
      <div class="uv-current">
      <h2>${t("home.uv_now")}${statusBadge(block?.status)}</h2>
      ${block?.data ? `
      <div class="big uv-reading">${uvChip(reading?.value)} <span class="uv-reading-meta">
        ${time ? `<span class="muted uv-at">${esc(t("home.uv_at", { time }))}</span>` : ""}
        <span class="muted">${level ? t(`uv.levels.${level}`) : ""}</span>
      </span></div>` : `<p class="muted">${t("weather.no_data")}</p>`}
      </div>
      ${block?.data ? `
      ${uv.max !== null && uv.max !== undefined
        ? `<div class="muted uv-maximum">${t("home.uv_max", { v: num(uv.max, 1), time: uv.max_time })}</div>`
        : ""}
      <p class="uv-protection"><strong>${protection}</strong></p>` : ""}
      </a>
      <div class="mini-chart" id="home-uv-chart"></div>
    </section>`;
}

function rainCard(block) {
  return `<section class="card wide rain-card">
    <h2><a href="#/weather">${t("home.rain_hours")}</a>${statusBadge(block?.status)}</h2>
    <div class="mini-chart" id="home-rain-chart"></div>
  </section>`;
}

function rainForecasts(summary, weather) {
  const sources = Object.entries(SOURCE_COLORS).map(([key, color]) => {
    const block = weather?.forecasts?.[key] ?? (key === "openmeteo" ? summary.today : null);
    const data = block?.data?.hourly ?? (Array.isArray(block?.data) ? block.data : []);
    const rows = upcomingHours(summary, { data })
      .filter((row) => Number.isFinite(new Date(row.time).getTime()));
    return { block, color, label: block?.source?.label ?? key, rows };
  });
  const rows = [...new Map(sources.flatMap((source) => source.rows)
    .map((row) => [row.time, row])).values()]
    .sort((left, right) => left.time.localeCompare(right.time));
  const series = sources.map((source) => {
    const values = new Map(source.rows.map((row) => [row.time, row.precipitation_probability]));
    return {
      label: source.label, color: source.color,
      values: rows.map((row) => Number.isFinite(values.get(row.time)) ? values.get(row.time) : null),
    };
  }).filter((source) => source.values.some(Number.isFinite));
  const status = !series.length ? "error"
    : sources.some((source) => source.block?.status === "stale"
      && source.rows.some((row) => Number.isFinite(row.precipitation_probability))) ? "stale" : "ok";
  return { rows, series, status };
}

function miniChart(root, selector, rows, field, label, color, yMax, options = {}) {
  const container = root.querySelector?.(selector);
  if (!container) return;
  const points = rows.filter((row) => (options.series || Number.isFinite(row[field]))
    && Number.isFinite(new Date(row.time).getTime()));
  if (!points.length || options.series?.length === 0) {
    container.innerHTML = `<p class="muted">${t("weather.no_data")}</p>`;
    return;
  }
  const xs = points.map((row) => forecastTime(row.time, options.timeZone));
  const hour = (value) => new Intl.DateTimeFormat("es-ES", {
    timeZone: options.timeZone, hour: "2-digit", minute: "2-digit",
  }).format(new Date(value));
  renderChart(container, {
    compact: true,
    ariaLabel: label,
    x: xs,
    series: [{
      label: field === "uv" ? t("uv.series") : t("home.rain_prob"),
      color, values: points.map((row) => row[field]),
      tension: field === "uv" ? 0 : undefined,
    }],
    yMin: 0,
    yMax,
    xTicks: [xs[0], xs[Math.floor(xs.length / 2)], xs[xs.length - 1]]
      .filter((value, index, ticks) => ticks.indexOf(value) === index),
    xFormat: hour,
    titleFormat: hour,
    valueFormat: (value) => field === "uv" ? num(value, 1) : t("units.probability", { v: num(value) }),
    yFormat: field === "uv" ? undefined : (value) => t("units.probability", { v: num(value) }),
    ...options,
  });
}

function riverCard(summary) {
  const block = summary.river;
  const data = block?.data;
  const flowStatus = ["safe", "caution", "danger"].includes(block?.flow_status)
    ? block.flow_status : "unknown";
  const flowColor = {
    safe: UV_COLORS.low, caution: UV_COLORS.moderate, danger: UV_COLORS.very_high,
  }[flowStatus];
  const body = data
    ? `
      <div class="big"><span class="flow-chip ${flowStatus}"${flowColor ? ` style="background:${flowColor};color:#111"` : ""}>${t("units.flow", { v: num(data.flow_m3s, 2) })}</span></div>
      ${flowStatus !== "unknown" ? `<div class="muted flow-status">${t(`river.flow_status.${flowStatus}`)}</div>` : ""}
      ${data.trend ? `<div class="muted river-trend">${t(`river.trend.${data.trend}`)}</div>` : ""}
      <div class="muted river-reading">${t("home.river_reading", { age: age(data.time) })}</div>`
    : "";
  return `
    <a class="card" href="#/river">
      <h2>${t("home.river_now")}${statusBadge(block?.status)}</h2>
      ${body}
    </a>`;
}

function solarDay(summary) {
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: summary.location?.timezone,
    year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
  return loadSunTimes(summary.location, today);
}

function solarHour(value, summary) {
  return value && Number.isFinite(Date.parse(value))
    ? esc(new Intl.DateTimeFormat("es-ES", {
      timeZone: summary.location.timezone, hour: "2-digit", minute: "2-digit",
    }).format(new Date(value))) : t("weather.no_data");
}

function sunTimes(summary, day) {
  if (!day) return t("home.sun_unavailable");
  const hour = (value) => solarHour(value, summary);
  return `<span>${t("home.sunrise")}: ${hour(day.civil_twilight_begin)} - ${hour(day.sunrise)}</span>
    <span>${t("home.sunset")}: ${hour(day.sunset)} - ${hour(day.civil_twilight_end)}</span>`;
}

export async function render(root) {
  const summary = await loadData("summary");
  const weather = await loadData("weather").catch(() => null);
  const uvFile = await loadData("uv").catch(() => null);
  const forecast = weather?.forecasts?.openmeteo;
  const block = forecast?.data?.hourly
    ? { status: forecast.status, data: forecast.data.hourly } : summary.today;
  const hours = upcomingHours(summary, block);
  const rain = rainForecasts(summary, weather);
  root.innerHTML = `
    <div class="grid home-grid">
      ${weatherNowCard(summary)}
      ${riverCard(summary)}
      ${restOfDayCard(block, hours)}
      ${rainCard(rain)}
      ${uvCard(summary, uvFile)}
    </div>
    <nav class="home-links">
      <a class="next-days-link" href="#/weather/days">${t("home.next_days")}</a>
    </nav>`;
  const day = await solarDay(summary).catch(() => null);
  const xs = rain.rows.map((row) => forecastTime(row.time, summary.location.timezone));
  const night = civilNightRanges(xs, day, summary.location.timezone);
  miniChart(root, "#home-rain-chart", rain.rows, "precipitation_probability",
    t("home.rain_chart_label"), SOURCE_COLORS.openmeteo, 100, {
      series: rain.series,
      xRanges: night, timeZone: summary.location.timezone,
    });
  try {
    const uvDay = uvFile?.data?.date && uvFile.data.date !== day?.date
      ? await loadSunTimes(summary.location, uvFile.data.date) : day;
    const uvStart = new Date(uvDay?.civil_twilight_begin ?? "").getTime();
    const uvEnd = new Date(uvDay?.civil_twilight_end ?? "").getTime();
    const daylight = Number.isFinite(uvStart) && Number.isFinite(uvEnd)
      && uvStart < uvEnd;
    const reading = selectUvReading(uvFile?.data?.hourly, summary.location.timezone);
    miniChart(root, "#home-uv-chart", daylight ? uvFile?.data?.hourly ?? [] : [], "uv",
      t("uv.chart_label"), "#b26a00", Math.max(4, Math.ceil(uvFile?.data?.max ?? 0) + 1), {
        xMin: uvStart, xMax: uvEnd,
        timeZone: summary.location.timezone,
        now: Date.now(),
        dots: reading
          ? [{ x: reading.time, y: reading.value, color: UV_COLORS[uvLevel(reading.value)] }]
          : [],
        xTicks: [uvStart, (uvStart + uvEnd) / 2, uvEnd],
        yZones: UV_ZONES.map((zone) => ({
          from: zone.from, to: zone.to, color: UV_COLORS[zone.level],
        })),
      });
  } catch {
    miniChart(root, "#home-uv-chart", [], "uv", t("uv.chart_label"), "#b26a00", 4);
  }
  const solar = root.ownerDocument?.getElementById("sun-times");
  if (solar && root.isConnected !== false) {
    solar.innerHTML = sunTimes(summary, day);
    solar.hidden = false;
  }
}

export async function renderSun(root) {
  const summary = await loadData("summary");
  let day;
  try {
    day = await solarDay(summary);
  } catch {
    root.innerHTML = `<a class="back" href="#/">${t("back")}</a>
      <h1>${t("sun.title")}</h1><p class="notice">${t("home.sun_unavailable")}</p>`;
    return;
  }
  const date = new Intl.DateTimeFormat("es-ES", {
    timeZone: "UTC", weekday: "long", day: "numeric", month: "long",
    year: "numeric",
  }).format(new Date(`${day.date}T12:00:00Z`));
  const displayDate = `${date[0].toLocaleUpperCase("es-ES")}${date.slice(1)}`;
  const events = [
    ["astronomical", "astronomical_twilight_begin", "astronomical_twilight_end"],
    ["nautical", "nautical_twilight_begin", "nautical_twilight_end"],
    ["civil", "civil_twilight_begin", "civil_twilight_end"],
    ["sun", "sunrise", "sunset"],
  ].reverse().filter(([, begin, end]) => begin in day || end in day);
  root.innerHTML = `<a class="back" href="#/">${t("back")}</a>
    <h1>${t("sun.title")}</h1>
    <p class="muted">${esc(displayDate)}</p>
    <table class="days sun-details">
      <thead><tr><th>${t("sun.event")}</th><th>${t("home.sunrise")}</th><th>${t("home.sunset")}</th></tr></thead>
      <tbody>${events.map(([label, begin, end]) => `<tr>
        <th scope="row">${t(`sun.${label}`)}</th>
        <td>${solarHour(day[begin], summary)}</td>
        <td>${solarHour(day[end], summary)}</td>
      </tr>`).join("")}</tbody>
    </table>
    <p>${t("home.sun_source")}</p>`;
}

export function renderCsck(root) {
  root.innerHTML = `<a class="back" href="#/">${t("back")}</a>
    <h1>${t("home.csck")}</h1><p class="muted">${t("csck.pending")}</p>`;
}
