// Thin wrapper around the vendored Chart.js (window.Chart, see
// vendor/chartjs/README.md). Views describe WHAT to draw; this module
// decides HOW. It is the only place that touches Chart.js.
//
// All series of one chart share the same x array (epoch ms or any number),
// so touching the chart shows every value at that x in one tooltip.

const instances = new WeakMap();

function css(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** Background horizontal zones, shaded x ranges and a "now" line. */
const decorations = {
  id: "decorations",
  beforeDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea: area, scales: { x, y } } = chart;
    ctx.save();
    for (const zone of opts.yZones ?? []) {
      const top = y.getPixelForValue(Math.min(zone.to, y.max));
      const bottom = y.getPixelForValue(Math.max(zone.from, y.min));
      if (bottom <= top) continue;
      ctx.fillStyle = zone.color;
      ctx.globalAlpha = 0.2;
      ctx.fillRect(area.left, top, area.right - area.left, bottom - top);
    }
    for (const range of opts.xRanges ?? []) {
      const left = Math.max(area.left, x.getPixelForValue(range.from));
      const right = Math.min(area.right, x.getPixelForValue(range.to));
      if (right <= left) continue;
      ctx.fillStyle = range.color;
      ctx.globalAlpha = 0.15;
      ctx.fillRect(left, area.top, right - left, area.bottom - area.top);
    }
    ctx.restore();
  },
  afterDatasetsDraw(chart, _args, opts) {
    const { ctx, chartArea: area, scales: { x } } = chart;
    ctx.save();
    ctx.strokeStyle = css("--text", "#333");
    ctx.lineWidth = 1;
    const lines = [];
    if (Number.isFinite(opts.now)) lines.push({ value: opts.now, dash: [3, 3] });
    // Crosshair at the touched/hovered position.
    const active = chart.tooltip?.getActiveElements?.() ?? [];
    if (active.length) lines.push({ pixel: active[0].element.x, dash: [], alpha: 0.4 });
    for (const line of lines) {
      const px = line.pixel ?? x.getPixelForValue(line.value);
      if (px < area.left || px > area.right) continue;
      ctx.globalAlpha = line.alpha ?? 0.8;
      ctx.setLineDash(line.dash);
      ctx.beginPath();
      ctx.moveTo(px, area.top);
      ctx.lineTo(px, area.bottom);
      ctx.stroke();
    }
    // Highlighted points (e.g. the latest reading), drawn on top.
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
    for (const dot of opts.dots ?? []) {
      if (!Number.isFinite(dot.y) || !Number.isFinite(dot.x)) continue;
      const px = x.getPixelForValue(dot.x);
      const py = chart.scales.y.getPixelForValue(dot.y);
      if (px < area.left - 1 || px > area.right + 1) continue;
      ctx.beginPath();
      ctx.arc(px, py, 5, 0, 2 * Math.PI);
      ctx.fillStyle = dot.color;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = "#fff";
      ctx.stroke();
    }
    ctx.restore();
  },
};

/**
 * Draw (or redraw) a chart inside `container`.
 *
 * spec = {
 *   x: number[],                                   shared x values
 *   series: [{ label, color, values, dashed, width, spanGaps, tooltip }],
 *   band:   { label, color, lower: [], upper: [] } percentile band (optional)
 *   bands:  [{ label, color, lower, upper, opacity, order }] layered bands
 *   dots:   [{ x, y, color, label }]               highlighted points
 *   yZones: [{ from, to, color }], xRanges: [{ from, to, color }], now,
 *   xMin, xMax, yMin, yMax, xTicks: number[],
 *   xFormat(x) -> tick label, titleFormat(x) -> tooltip title,
 *   valueFormat(y) -> tooltip value, ariaLabel
 * }
 */
export function renderChart(container, spec) {
  instances.get(container)?.destroy();
  const wrapper = document.createElement("div");
  wrapper.className = "chart-canvas";
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  if (spec.ariaLabel) canvas.setAttribute("aria-label", spec.ariaLabel);
  wrapper.appendChild(canvas);
  container.replaceChildren(wrapper);

  const xs = spec.x;
  const points = (values) => xs.map((x, i) => ({ x, y: values[i] ?? null }));
  const datasets = [];
  const bands = spec.bands ?? (spec.band ? [spec.band] : []);
  for (const band of bands) {
    const lowerDatasetIndex = datasets.length;
    datasets.push({
      label: "band-lower", data: points(band.lower), role: "band-lower",
      borderWidth: 0, pointRadius: 0, pointHoverRadius: 0, fill: false,
      order: band.order ?? 100,
    });
    datasets.push({
      label: band.label, data: points(band.upper), role: "band-upper",
      borderWidth: 0, pointRadius: 0, pointHoverRadius: 0,
      backgroundColor: hexAlpha(band.color, band.opacity ?? 0.3), fill: "-1",
      order: band.order ?? 100, lowerDatasetIndex, bandColor: band.color,
    });
  }
  for (const s of spec.series) {
    datasets.push({
      label: s.label, data: points(s.values), role: s.tooltip === false ? "hidden" : "series",
      borderColor: s.color, backgroundColor: s.color, borderWidth: s.width ?? 2,
      borderDash: s.dashed ? [6, 4] : [], pointRadius: s.pointRadius ?? 0, pointHoverRadius: 4,
      showLine: s.showLine ?? true,
      order: s.order ?? 0,
      spanGaps: s.spanGaps ?? false, fill: false, tension: s.tension ?? 0.15,
    });
  }
  const muted = css("--muted", "#666");
  const grid = css("--border", "#ddd");
  const valueFormat = spec.valueFormat ?? ((v) => String(v));
  const chart = new window.Chart(canvas, {
    type: "line",
    data: { datasets },
    plugins: [decorations],
    options: {
      animation: false,
      maintainAspectRatio: false,
      parsing: false,
      normalized: true,
      // Touch: tap or drag a finger to inspect; mouse: hover.
      events: ["mousemove", "mouseout", "click", "touchstart", "touchmove"],
      interaction: { mode: "index", intersect: false, axis: "x" },
      scales: {
        x: {
          type: "linear",
          min: spec.xMin ?? xs[0],
          max: spec.xMax ?? xs[xs.length - 1],
          grid: { color: grid },
          ticks: {
            color: muted, maxRotation: 0, autoSkip: true, autoSkipPadding: 8,
            font: spec.compact ? { size: 11 } : undefined,
            callback: (value) => (spec.xFormat ? spec.xFormat(value) : value),
          },
          afterBuildTicks: (scale) => {
            if (spec.xTicks) scale.ticks = spec.xTicks.map((value) => ({ value }));
          },
        },
        y: {
          min: spec.yMin,
          max: spec.yMax,
          grace: "5%",
          grid: { color: grid },
          ticks: {
            color: muted, maxTicksLimit: spec.compact ? 3 : 6,
            font: spec.compact ? { size: 11 } : undefined,
            callback: spec.yFormat,
          },
        },
      },
      plugins: {
        legend: { display: false },
        decorations: {
          yZones: spec.yZones, xRanges: spec.xRanges, now: spec.now, dots: spec.dots,
        },
        tooltip: {
          backgroundColor: css("--card", "#fff"),
          titleColor: css("--text", "#111"),
          bodyColor: css("--text", "#111"),
          borderColor: grid,
          borderWidth: 1,
          padding: 6,
          titleFont: { size: 12 },
          bodyFont: { size: 11 },
          boxPadding: 4,
          usePointStyle: true,
          filter: (item) => ["series", "band-upper"].includes(item.dataset.role)
            && item.raw?.y !== null && item.raw?.y !== undefined,
          callbacks: {
            title: (items) => (items.length && spec.titleFormat
              ? spec.titleFormat(items[0].raw.x) : ""),
            label: (item) => {
              if (item.dataset.role === "band-upper") {
                const lower = item.chart.data.datasets[item.dataset.lowerDatasetIndex].data[item.dataIndex]?.y;
                return ` ${item.dataset.label}: ${valueFormat(lower)} – ${valueFormat(item.raw.y)}`;
              }
              return ` ${item.dataset.label}: ${valueFormat(item.raw.y)}`;
            },
            labelColor: (item) => ({
              borderColor: item.dataset.borderColor ?? item.dataset.bandColor,
              backgroundColor: item.dataset.role === "band-upper"
                ? item.dataset.bandColor : item.dataset.borderColor,
            }),
          },
        },
      },
    },
  });
  instances.set(container, chart);
  if (!spec.compact && spec.showLegend !== false) container.appendChild(legend(spec));
  return chart;
}

function legend(spec) {
  const box = document.createElement("div");
  box.className = "legend";
  const items = [
    ...(spec.bands ?? (spec.band ? [spec.band] : []))
      .map((band) => ({ ...band, isBand: true })),
    ...spec.series.filter((s) => s.label),
    ...(spec.dots ?? []).filter((d) => d.label).map((d) => ({ ...d, isDot: true })),
  ];
  for (const item of items) {
    const span = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.style.background = item.dashed
      ? `repeating-linear-gradient(90deg, ${item.color} 0 4px, transparent 4px 7px)`
      : item.color;
    if (item.isBand) swatch.style.height = "0.6rem";
    if (item.isDot) swatch.className = "dot";
    span.append(swatch, item.label);
    box.appendChild(span);
  }
  return box;
}

function hexAlpha(hex, alpha) {
  const value = hex.replace("#", "");
  const n = parseInt(value.length === 3 ? value.replace(/./g, "$&$&") : value, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

/** Tick positions every `stepMs` aligned to local midnight. */
export function timeTicks(x0, x1, stepMs) {
  const start = new Date(x0);
  start.setHours(0, 0, 0, 0);
  const ticks = [];
  for (let t = start.getTime(); t <= x1; t += stepMs) if (t >= x0) ticks.push(t);
  return ticks;
}
