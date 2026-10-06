import { loadData } from "../data.js";
import {
  age, dayLabel, esc, hourLabel, num, statusBadge, uvChip, uvLevel, wmoIcon, wmoText,
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
    ? t("home.observed_at", { station: esc(data.station_name ?? obs.source?.label), age: age(data.time) })
    : t("home.model_fallback");
  const details = [
    data.apparent_temperature !== undefined && data.apparent_temperature !== null
      ? t("home.feels_like", { v: t("units.temperature", { v: num(data.apparent_temperature) }) })
      : "",
    t("home.humidity", { v: t("units.humidity", { v: num(data.humidity) }) }),
    t("home.wind", { v: t("units.wind", { v: num(data.wind_speed) }) }),
  ].filter(Boolean);
  return `
    <a class="card" href="#/weather">
      <h2>${t("home.weather_now")}${statusBadge(status)}</h2>
      <div class="big">${icon} ${t("units.temperature", { v: num(data.temperature, 1) })}</div>
      ${useObs ? "" : `<div>${esc(wmoText(data.weather_code))}</div>`}
      <div class="row muted">${details.map((d) => `<span>${d}</span>`).join("")}</div>
      <div class="muted">${caption}</div>
    </a>`;
}

function restOfDayCard(summary) {
  const block = summary.today;
  const nowKey = new Date();
  nowKey.setMinutes(0, 0, 0);
  const hours = (block?.data ?? []).filter((h) => new Date(h.time) >= nowKey);
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
    <a class="card wide" href="#/weather">
      <h2>${t("home.rest_of_day")}${statusBadge(block?.status)}</h2>
      ${content}
    </a>`;
}

function uvCard(summary) {
  const block = summary.uv;
  const uv = block?.data ?? {};
  if (block?.status === "error" && !uv.hourly && uv.max == null) {
    return `<a class="card" href="#/uv"><h2>${t("home.uv_now")}${statusBadge("error")}</h2></a>`;
  }
  const protection = uv.protection
    ? t("uv.protection_window", { from: uv.protection.from, to: uv.protection.to })
    : t("uv.protection_none");
  const level = uvLevel(uv.now);
  return `
    <a class="card" href="#/uv">
      <h2>${t("home.uv_now")}${statusBadge(block?.status)}</h2>
      <div class="big">${uvChip(uv.now)} <span class="muted">${level ? t(`uv.levels.${level}`) : ""}</span></div>
      <p><strong>${protection}</strong></p>
      ${uv.max !== null && uv.max !== undefined
        ? `<div class="muted">${t("home.uv_max", { v: num(uv.max, 1), time: uv.max_time })}</div>`
        : ""}
    </a>`;
}

function riverCard(summary) {
  const block = summary.river;
  const data = block?.data;
  const body = data
    ? `
      <div class="row">
        <div><div class="muted">${t("river.flow")}</div><div class="big">${num(data.flow_m3s, 2)}</div><div class="muted">m³/s</div></div>
        <div><div class="muted">${t("river.level")}</div><div class="big">${num(data.level_m, 2)}</div><div class="muted">m</div></div>
      </div>
      <div class="row muted">
        ${data.trend ? `<span>${t(`river.trend.${data.trend}`)}</span>` : ""}
        <span>${t("home.river_reading", { age: age(data.time) })}</span>
      </div>`
    : "";
  return `
    <a class="card" href="#/river">
      <h2>${t("home.river_now")}${statusBadge(block?.status)}</h2>
      ${body}
    </a>`;
}

function nextDaysCard(summary) {
  const block = summary.next_days;
  const rows = (block?.data ?? []).map((d) => `
    <tr class="day">
      <td>${dayLabel(d.date)}</td>
      <td class="icon" title="${esc(wmoText(d.weather_code))}">${wmoIcon(d.weather_code)}</td>
      <td><strong>${num(d.temperature_max)}°</strong> / ${num(d.temperature_min)}°</td>
      <td class="muted">${num(d.precipitation_probability)}%</td>
      <td>${uvChip(d.uv_max)}</td>
    </tr>`).join("");
  return `
    <a class="card wide" href="#/weather">
      <h2>${t("home.next_days")}${statusBadge(block?.status)}</h2>
      <table class="days"><tbody>${rows}</tbody></table>
    </a>`;
}

export async function render(root) {
  const summary = await loadData("summary");
  root.innerHTML = `
    <div class="grid">
      ${weatherNowCard(summary)}
      ${uvCard(summary)}
      ${restOfDayCard(summary)}
      ${riverCard(summary)}
      ${nextDaysCard(summary)}
    </div>`;
}
