import { renderChart } from "../charts.js";
import { loadData, loadSunTimes } from "../data.js";
import {
  esc, forecastTime, num, selectUvReading, statusBadge, UV_COLORS, UV_ZONES, uvChip, uvLevel,
} from "../format.js";
import { t } from "../i18n.js";

export async function render(root) {
  const file = await loadData("uv");
  const uv = file.data ?? {};
  const timezone = file.location.timezone;
  const hourly = (uv.hourly ?? []).filter((row) => typeof row.time === "string"
    && Number.isFinite(new Date(row.time).getTime()));
  const xs = hourly.map((row) => forecastTime(row.time, timezone));
  const values = hourly.map((row) => row.uv);
  const protection = uv.protection
    ? t("uv.protection_window", { from: uv.protection.from, to: uv.protection.to })
    : t("uv.protection_none");
  const reading = selectUvReading(hourly, timezone);
  const level = uvLevel(reading?.value);
  const hourFormat = new Intl.DateTimeFormat("es-ES", {
    timeZone: timezone, hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  const time = reading ? hourFormat.format(reading.time) : "";

  if (!xs.length) {
    root.innerHTML = `
      <a class="back" href="#/">${t("back")}</a>
      <h1>${t("uv.title")} ${statusBadge(file.status)}</h1>
      <p class="muted">${t("weather.no_data")}</p>`;
    return;
  }
  root.innerHTML = `
    <a class="back" href="#/">${t("back")}</a>
    <h1>${t("uv.title")} ${statusBadge(file.status)}</h1>
    <div class="big uv-reading">${uvChip(reading?.value)} <span class="uv-reading-meta">
      ${time ? `<span class="muted uv-at">${esc(t("home.uv_at", { time }))}</span>` : ""}
      <span class="muted">${level ? t(`uv.levels.${level}`) : ""}</span>
    </span></div>
    <p><strong>${protection}</strong></p>
    <p class="muted">${t("uv.source_note")}</p>
    <p class="chart-hint">${t("chart_hint")}</p>
    <section class="card"><div id="uv-chart"></div></section>
    <div class="legend">${UV_ZONES.map((z) => `<span><i style="background:${UV_COLORS[z.level]};height:.6rem"></i>${t(`uv.levels.${z.level}`)}</span>`).join("")}</div>
    <p class="muted">${t("uv.source", { source: esc(file.source?.label ?? "") })}</p>`;

  const container = root.querySelector("#uv-chart");
  const solar = await loadSunTimes(file.location, uv.date).catch(() => null);
  const dawn = new Date(solar?.civil_twilight_begin ?? "").getTime();
  const dusk = new Date(solar?.civil_twilight_end ?? "").getTime();
  if (!Number.isFinite(dawn) || !Number.isFinite(dusk) || dawn >= dusk) {
    container.innerHTML = `<p class="muted">${t("weather.no_data")}</p>`;
    return;
  }
  renderChart(container, {
    ariaLabel: t("uv.chart_label"),
    showLegend: false,
    x: xs,
    series: [{ label: t("uv.series"), color: "#b26a00", values, width: 2.5, tension: 0 }],
    yZones: UV_ZONES.map((z) => ({ from: z.from, to: z.to, color: UV_COLORS[z.level] })),
    xMin: dawn,
    xMax: dusk,
    yMin: 0,
    yMax: Math.max(4, Math.ceil(uv.max ?? 0) + 1),
    now: Date.now(),
    dots: reading
      ? [{ x: reading.time, y: reading.value, color: UV_COLORS[level] }]
      : [],
    xTicks: [dawn, (dawn + dusk) / 2, dusk],
    xFormat: (x) => hourFormat.format(x),
    titleFormat: (x) => hourFormat.format(x),
    valueFormat: (v) => `${num(v, 1)} · ${t(`uv.levels.${uvLevel(v)}`)}`,
  });
}
