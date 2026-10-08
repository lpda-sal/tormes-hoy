import { renderChart, timeTicks } from "../charts.js";
import { loadData } from "../data.js";
import { dateLabel, dateTimeLabel, esc, num, statusBadge, UV_COLORS } from "../format.js";
import { t } from "../i18n.js";

const DAY = 86400000;
const COLORS = {
  current: "#e07a1f",
  previous: "#1f5f8b",
  median: "#555555",
  band: "#8fa9bf",
  extrema: "#9aa6a0",
  now: "#d1495b",
};
const UNITS = { flow_m3s: " m³/s", level_m: " m" };
const LABEL_KEYS = { flow_m3s: "flow", level_m: "level" };

// Calendar axis: one slot per day of a leap year (0 = 1 Jan, 59 = 29 Feb,
// 365 = 31 Dec), so every year is drawn on the same 1 Jan – 31 Dec axis.
const REF_YEAR = 2000;
const SLOTS = 366;
const MONTH_STARTS = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];

const state = { variable: "flow_m3s", range: "year" };

function slotOf(date) {
  return Math.round(
    (Date.UTC(REF_YEAR, date.getMonth(), date.getDate()) - Date.UTC(REF_YEAR, 0, 1)) / DAY,
  );
}

function slotDate(slot) {
  return new Date(REF_YEAR, 0, 1 + slot, 12);
}

function mdOf(date) {
  return `${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function yearbookFor(yearbook, variable) {
  const block = yearbook?.variables?.[variable];
  if (!block?.stats?.length) return null;
  return { ...block, byMd: new Map(block.stats.map((s) => [s.md, s])) };
}

/** Daily observed means of one calendar year, by slot. */
function yearValues(daily, variable, year) {
  const values = new Array(SLOTS).fill(null);
  for (const day of daily) {
    if (!day.date.startsWith(`${year}-`)) continue;
    const mean = day[variable]?.mean;
    if (mean !== undefined && mean !== null) {
      values[slotOf(new Date(`${day.date}T12:00`))] = mean;
    }
  }
  return values;
}

function segmented(name, options, current) {
  return `<div class="segmented" role="group">${options.map(([value, label]) =>
    `<button type="button" data-${name}="${value}" aria-pressed="${value === current}">${label}</button>`).join("")}</div>`;
}

function yearbookParts(stats, keyOf) {
  if (!stats) return { bands: [], series: [] };
  const bands = [{
    label: t("river.quartiles", { period: stats.period }),
    color: COLORS.band,
    lower: keyOf.map((md) => stats.byMd.get(md)?.p25 ?? null),
    upper: keyOf.map((md) => stats.byMd.get(md)?.p75 ?? null),
  }];
  if (keyOf.some((md) => {
    const row = stats.byMd.get(md);
    return Number.isFinite(row?.min) && Number.isFinite(row?.max);
  })) {
    bands.unshift({
      label: t("river.extrema", { period: stats.period }),
      color: COLORS.extrema, opacity: 0.18, order: 101,
      lower: keyOf.map((md) => stats.byMd.get(md)?.min ?? null),
      upper: keyOf.map((md) => stats.byMd.get(md)?.max ?? null),
    });
  }
  return {
    bands,
    series: [{
      label: t("river.median", { period: stats.period }),
      color: COLORS.median,
      dashed: true,
      width: 1.5,
      values: keyOf.map((md) => stats.byMd.get(md)?.p50 ?? null),
    }],
  };
}

function yearSpec(files, variable) {
  const now = new Date();
  const year = now.getFullYear();
  const daily = files.daily?.daily ?? [];
  const xs = Array.from({ length: SLOTS }, (_, i) => i);
  const stats = yearbookFor(files.yearbook, variable);
  const { bands, series } = yearbookParts(stats, xs.map((i) => mdOf(slotDate(i))));

  const previous = yearValues(daily, variable, year - 1);
  const current = yearValues(daily, variable, year);
  // Bridge only the 29 Feb slot in non-leap years (gap of 2 slots).
  series.push(
    { label: t("river.year_label", { year: year - 1 }), color: COLORS.previous, values: previous, width: 1.8, spanGaps: 2 },
    { label: t("river.year_label", { year }), color: COLORS.current, values: current, width: 2.4, spanGaps: 2 },
  );

  const reading = files.raw?.current?.data;
  return {
    x: xs,
    bands,
    series,
    xMin: 0,
    xMax: SLOTS - 1,
    now: slotOf(now),
    dots: reading ? [{ x: slotOf(new Date(reading.time)), y: reading[variable], color: COLORS.now, label: t("river.now") }] : [],
    xTicks: MONTH_STARTS,
    xFormat: (slot) => slotDate(slot).toLocaleDateString("es-ES", { month: "short" }),
    titleFormat: (slot) => dateLabel(slotDate(slot)),
  };
}

function monthSpec(files, variable) {
  const today = new Date();
  const year = today.getFullYear();
  const dates = Array.from({ length: 31 }, (_, index) =>
    new Date(year, today.getMonth(), today.getDate() - 30 + index, 12));
  const xs = dates.map((date) => date.getTime());
  const daily = new Map((files.daily?.daily ?? []).map((day) => [day.date, day]));
  const stats = yearbookFor(files.yearbook, variable);
  const { bands, series } = yearbookParts(stats, xs.map((x) => mdOf(new Date(x))));
  for (const offset of [1, 0]) {
    const values = dates.map((date) => {
      const compared = new Date(date);
      compared.setFullYear(date.getFullYear() - offset);
      if (compared.getMonth() !== date.getMonth()) return null;
      const key = `${compared.getFullYear()}-${mdOf(compared)}`;
      const mean = daily.get(key)?.[variable]?.mean;
      return Number.isFinite(mean) ? mean : null;
    });
    series.push({
      label: t("river.year_label", { year: year - offset }),
      color: offset ? COLORS.previous : COLORS.current,
      values, width: offset ? 1.8 : 2.4, spanGaps: DAY,
      pointRadius: values.filter((value) => value !== null).length === 1 ? 3 : 0,
    });
  }
  const reading = files.raw?.current?.data;
  return {
    x: xs,
    bands,
    series,
    xMin: xs[0] - DAY / 2,
    xMax: xs[xs.length - 1] + DAY / 2,
    now: Date.now(),
    dots: reading ? [{ x: new Date(reading.time).getTime(), y: reading[variable], color: COLORS.now, label: t("river.now") }] : [],
    xTicks: timeTicks(xs[0], xs[xs.length - 1], 7 * DAY),
    xFormat: (x) => dateLabel(x),
    titleFormat: (x) => dateTimeLabel(x),
  };
}

function draw(root, files) {
  const variable = state.variable;
  const notices = [];
  const stats = yearbookFor(files.yearbook, variable);
  if (!stats) notices.push(t("river.no_yearbook"));
  else if (stats.detected_shifts?.length) notices.push(t("river.shift_notice", { period: stats.period }));

  const spec = state.range === "month"
    ? monthSpec(files, variable)
    : yearSpec(files, variable);

  root.querySelector("#river-controls").innerHTML =
    segmented("variable", [["flow_m3s", t("river.flow")], ["level_m", t("river.level")]], state.variable) +
    segmented("range", [["month", t("river.last_month")], ["year", t("river.by_year")]], state.range);
  root.querySelector("#river-unit").textContent =
    `${t(`river.${LABEL_KEYS[variable]}`)} (${UNITS[variable].trim()})`;
  root.querySelector("#river-notices").innerHTML =
    [...new Set(notices)].map((n) => `<p class="notice muted">${esc(n)}</p>`).join("");

  const container = root.querySelector("#river-chart");
  if (!spec.x.length) {
    container.innerHTML = "";
    return;
  }
  renderChart(container, {
    ...spec,
    ariaLabel: t(`river.${LABEL_KEYS[variable]}`),
    valueFormat: (v) => `${num(v, 2)}${UNITS[variable]}`,
  });
}

export async function render(root) {
  const [raw, daily, yearbook, summary] = await Promise.all([
    loadData("river-observed-30d"),
    loadData("river-observed-daily"),
    loadData("river-yearbook-stats", { optional: true }),
    loadData("summary", { optional: true }).catch(() => null),
  ]);
  const current = raw?.current;
  const reading = current?.data;
  const summaryRiver = summary?.river;
  const sameReading = reading && reading.time === summaryRiver?.data?.time
    && reading.flow_m3s === summaryRiver.data.flow_m3s;
  const flowStatus = sameReading && Number.isFinite(reading.flow_m3s)
    && reading.flow_m3s >= 0
    && ["safe", "caution", "danger"].includes(summaryRiver.flow_status)
    ? summaryRiver.flow_status : "unknown";
  const flowColor = {
    safe: UV_COLORS.low, caution: UV_COLORS.moderate, danger: UV_COLORS.very_high,
  }[flowStatus];
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("river.title")} ${statusBadge(current?.status)}</h1>
    ${reading ? `<div class="river-current">
      <div>
        <h2>${t("river.flow")}</h2>
        <div class="big"><span class="flow-chip ${flowStatus}"${flowColor ? ` style="background:${flowColor};color:#111"` : ""}>${t("units.flow", { v: num(reading.flow_m3s, 2) })}</span></div>
        ${flowStatus !== "unknown" ? `<div class="muted flow-status">${t(`river.flow_status.${flowStatus}`)}</div>` : ""}
      </div>
      <div>
        <h2>${t("river.level")}</h2>
        <div class="big"><span class="level-chip">${num(reading.level_m, 2)}${UNITS.level_m}</span></div>
      </div>
    </div>` : `<p class="muted">${t("weather.no_data")}</p>`}
    <p class="chart-hint">${t("chart_hint")}</p>
    <section class="card">
      <div id="river-controls"></div>
      <h2 id="river-unit"></h2>
      <div id="river-chart"></div>
    </section>
    <div id="river-notices"></div>
    <p class="muted">${t("river.source")}</p>
    <p class="muted">${t("river.flow_status_note")}</p>`;
  const files = { raw, daily, yearbook };
  root.querySelector("#river-controls").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.variable) state.variable = button.dataset.variable;
    if (button.dataset.range) state.range = button.dataset.range;
    draw(root, files);
  });
  draw(root, files);
}
