import { t } from "./i18n.js";

const LOCALE = "es-ES";

/** Escape text coming from external data before inserting it as HTML. */
export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

export function num(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return Number(value).toLocaleString(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Parse "YYYY-MM-DDTHH:MM" (local, no offset) or full ISO strings. */
export function toDate(value) {
  return new Date(value);
}

export function hourLabel(value) {
  return toDate(value).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" });
}

export function forecastTime(value, timeZone) {
  if (/(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return new Date(value).getTime();
  const offset = new Intl.DateTimeFormat("en", {
    timeZone, timeZoneName: "longOffset",
  }).formatToParts(new Date(`${value}Z`)).find((part) => part.type === "timeZoneName").value;
  return new Date(`${value}${offset === "GMT" ? "Z" : offset.replace("GMT", "")}`).getTime();
}

export function selectUvReading(hourly, timeZone, now = Date.now()) {
  const distance = (reading) => Math.abs(reading.time - now);
  const nearest = (hourly ?? [])
    .filter((row) => Number.isFinite(row.uv) && typeof row.time === "string"
      && Number.isFinite(new Date(row.time).getTime()))
    .map((row) => ({ value: row.uv, time: forecastTime(row.time, timeZone) }))
    .filter((reading) => Number.isFinite(reading.time))
    .sort((left, right) => distance(left) - distance(right) || right.time - left.time)
    .slice(0, 2);
  return nearest.sort((left, right) => right.value - left.value
    || distance(left) - distance(right) || right.time - left.time)[0] ?? null;
}

export function civilNightRanges(xs, day, timeZone) {
  if (!xs.length || !day?.civil_twilight_begin || !day?.civil_twilight_end) return [];
  const dawn = new Date(day.civil_twilight_begin);
  const dusk = new Date(day.civil_twilight_end);
  if (!Number.isFinite(dawn.getTime()) || !Number.isFinite(dusk.getTime())) return [];
  const clock = new Intl.DateTimeFormat("en-GB", {
    timeZone, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  });
  const dates = new Intl.DateTimeFormat("en-CA", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
  });
  const cursor = new Date(`${dates.format(new Date(xs[0]))}T12:00:00Z`);
  const lastDate = dates.format(new Date(xs[xs.length - 1]));
  cursor.setUTCDate(cursor.getUTCDate() - 1);
  const ranges = [];
  while (cursor.toISOString().slice(0, 10) <= lastDate) {
    const date = cursor.toISOString().slice(0, 10);
    cursor.setUTCDate(cursor.getUTCDate() + 1);
    const tomorrow = cursor.toISOString().slice(0, 10);
    const from = forecastTime(`${date}T${clock.format(dusk)}`, timeZone);
    const to = forecastTime(`${tomorrow}T${clock.format(dawn)}`, timeZone);
    if (from < xs[xs.length - 1] && to > xs[0]) {
      ranges.push({ from, to, color: "#555" });
    }
  }
  return ranges;
}

export function dayLabel(value) {
  // "YYYY-MM-DD" strings are dates without time: read them at local noon.
  const date = typeof value === "string" && value.length === 10
    ? new Date(`${value}T12:00`)
    : new Date(value);
  const today = new Date();
  const tomorrow = new Date(today.getTime() + 86400000);
  if (date.toDateString() === today.toDateString()) return t("time.today");
  if (date.toDateString() === tomorrow.toDateString()) return t("time.tomorrow");
  return date.toLocaleDateString(LOCALE, { weekday: "short", day: "numeric" });
}

export function dateLabel(value) {
  return toDate(value).toLocaleDateString(LOCALE, { day: "numeric", month: "short" });
}

export function monthLabel(value) {
  return toDate(value).toLocaleDateString(LOCALE, { month: "short" });
}

export function dateTimeLabel(value) {
  return toDate(value).toLocaleString(LOCALE, {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

/** "hace 25 min" style age. */
export function age(value) {
  const minutes = Math.round((Date.now() - toDate(value).getTime()) / 60000);
  if (minutes < 1) return t("time.just_now");
  if (minutes < 60) return t("time.minutes_ago", { n: minutes });
  const hours = Math.round(minutes / 60);
  if (hours < 48) return t("time.hours_ago", { n: hours });
  return t("time.days_ago", { n: Math.round(hours / 24) });
}

export function statusBadge(status) {
  if (status === "stale") return `<span class="badge stale">${t("status.stale")}</span>`;
  if (status === "error") return `<span class="badge error">${t("status.error")}</span>`;
  return "";
}

// WMO weather interpretation codes (Open-Meteo) -> icon.
const WMO_ICONS = [
  [[0], "☀️"], [[1], "🌤️"], [[2], "⛅"], [[3], "☁️"], [[45, 48], "🌫️"],
  [[51, 53, 55, 56, 57], "🌦️"], [[61, 63, 65, 66, 67, 80, 81, 82], "🌧️"],
  [[71, 73, 75, 77, 85, 86], "🌨️"], [[95, 96, 99], "⛈️"],
];

export function wmoIcon(code) {
  const hit = WMO_ICONS.find(([codes]) => codes.includes(code));
  return hit ? hit[1] : "·";
}

export function wmoText(code) {
  return code === null || code === undefined ? "" : t(`wmo.${code}`);
}

// WHO UV index colours.
export const UV_COLORS = {
  low: "#3ea72d",
  moderate: "#fff300",
  high: "#f18b00",
  very_high: "#e53210",
  extreme: "#b567a4",
};

export const UV_ZONES = [
  { from: 0, to: 3, level: "low" },
  { from: 3, to: 6, level: "moderate" },
  { from: 6, to: 8, level: "high" },
  { from: 8, to: 11, level: "very_high" },
  { from: 11, to: 16, level: "extreme" },
];

export function uvLevel(value) {
  if (value === null || value === undefined) return null;
  return UV_ZONES.find((z) => value < z.to)?.level ?? "extreme";
}

export function uvChip(value) {
  const level = uvLevel(value);
  if (!level) return "–";
  return `<span class="uv-chip" style="background:${UV_COLORS[level]}">${num(value, 1)}</span>`;
}

// One colour per forecast source, shared by every chart and legend.
export const SOURCE_COLORS = {
  aemet: "#d1495b",
  openmeteo: "#1f77b4",
  meteoblue: "#2a9d8f",
};
