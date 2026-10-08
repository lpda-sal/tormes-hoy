import { renderChart } from "../charts.js";
import { loadData } from "../data.js";
import {
  esc, hourLabel, num, statusBadge, UV_COLORS, UV_ZONES, uvChip, uvLevel,
} from "../format.js";
import { t } from "../i18n.js";

const HOUR = 3600000;

export async function render(root) {
  const file = await loadData("uv");
  const uv = file.data ?? {};
  const xs = (uv.hourly ?? []).map((h) => new Date(h.time).getTime());
  const values = (uv.hourly ?? []).map((h) => h.uv);
  const dayStart = new Date(`${uv.date}T00:00`).getTime();
  const dayEnd = dayStart + 24 * HOUR;
  const protection = uv.protection
    ? t("uv.protection_window", { from: uv.protection.from, to: uv.protection.to })
    : t("uv.protection_none");
  const level = uvLevel(uv.now);

  if (!xs.length) {
    root.innerHTML = `
      <a class="back" href="#/">${t("back")}</a>
      <h1>${t("uv.title")} ${statusBadge(file.status)}</h1>
      <p class="card muted">${t("weather.no_data")}</p>`;
    return;
  }
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("uv.title")} ${statusBadge(file.status)}</h1>
    <section class="card">
      <div class="big">${uvChip(uv.now)} <span class="muted">${level ? t(`uv.levels.${level}`) : ""}</span></div>
      <p><strong>${protection}</strong></p>
      <p class="muted">${t("uv.protection_threshold", { v: num(uv.threshold) })}</p>
      <div id="uv-chart"></div>
      <p class="chart-hint">${t("chart_hint")}</p>
      <div class="legend">${UV_ZONES.map((z) => `<span><i style="background:${UV_COLORS[z.level]};height:.6rem"></i>${t(`uv.levels.${z.level}`)}</span>`).join("")}</div>
      <p class="muted">${t("uv.source_note", { source: esc(file.source?.label ?? "") })}</p>
    </section>`;

  const xRanges = uv.protection
    ? [{
      from: new Date(`${uv.date}T${uv.protection.from}`).getTime(),
      to: new Date(`${uv.date}T${uv.protection.to}`).getTime(),
      color: "#888",
    }]
    : [];
  renderChart(root.querySelector("#uv-chart"), {
    ariaLabel: t("uv.chart_label"),
    x: xs,
    series: [{ label: t("uv.series"), color: "#333", values, width: 2.5, tension: 0 }],
    yZones: UV_ZONES.map((z) => ({ from: z.from, to: z.to, color: UV_COLORS[z.level] })),
    xRanges,
    xMin: dayStart,
    xMax: dayEnd,
    yMin: 0,
    yMax: Math.max(4, Math.ceil(uv.max ?? 0) + 1),
    now: Date.now(),
    dots: [{ x: Date.now(), y: uv.now, color: UV_COLORS[level] ?? "#333" }],
    xTicks: Array.from({ length: 5 }, (_, i) => dayStart + i * 6 * HOUR),
    xFormat: (x) => hourLabel(x),
    titleFormat: (x) => hourLabel(x),
    valueFormat: (v) => `${num(v, 1)} · ${t(`uv.levels.${uvLevel(v)}`)}`,
  });
}
