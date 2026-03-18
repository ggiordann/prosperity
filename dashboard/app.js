const state = {
  outputDir: "outputs/imcdata",
  selectedLabel: null,
  runs: [],
  chart: {
    points: [],
    fills: [],
    viewStart: 0,
    viewEnd: 1,
    dragging: false,
    lastClientX: 0,
  },
};

const elements = {
  dataDir: document.getElementById("dataDir"),
  outputDir: document.getElementById("outputDir"),
  runSelect: document.getElementById("runSelect"),
  runButton: document.getElementById("runButton"),
  loadButton: document.getElementById("loadButton"),
  status: document.getElementById("status"),
  totalPnl: document.getElementById("totalPnl"),
  realizedPnl: document.getElementById("realizedPnl"),
  unrealizedPnl: document.getElementById("unrealizedPnl"),
  sharpeLike: document.getElementById("sharpeLike"),
  maxDrawdown: document.getElementById("maxDrawdown"),
  fillRatio: document.getElementById("fillRatio"),
  equityCanvas: document.getElementById("equityCanvas"),
  chartTitle: document.getElementById("chartTitle"),
  chartMeta: document.getElementById("chartMeta"),
};

elements.runButton.addEventListener("click", runBacktest);
elements.loadButton.addEventListener("click", loadExistingResults);
elements.runSelect.addEventListener("change", (event) => {
  if (event.target.value) {
    selectRun(event.target.value);
  }
});
elements.equityCanvas.addEventListener("wheel", onChartWheel, { passive: false });
elements.equityCanvas.addEventListener("mousedown", onChartMouseDown);
elements.equityCanvas.addEventListener("mousemove", onChartMouseMove);
elements.equityCanvas.addEventListener("mouseup", onChartMouseUp);
elements.equityCanvas.addEventListener("mouseleave", onChartMouseUp);
elements.equityCanvas.addEventListener("dblclick", resetChartView);

window.addEventListener("load", loadExistingResults);

async function runBacktest() {
  setBusy(true, "Running backtest...");
  try {
    const response = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataDir: elements.dataDir.value,
        outputDir: elements.outputDir.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      throw new Error(payload.error || "Backtest failed.");
    }
    state.outputDir = payload.output_dir;
    hydrateFromResultIndex({
      output_dir: payload.output_dir,
      runs: payload.runs,
    });
    setBusy(false, `Backtest completed for ${payload.runs.length} run(s).`);
  } catch (error) {
    setBusy(false, error.message || "Backtest failed.");
  }
}

async function loadExistingResults() {
  setBusy(true, "Loading outputs...");
  try {
    const outputDir = elements.outputDir.value;
    const response = await fetch(`/api/results?outputDir=${encodeURIComponent(outputDir)}`);
    const payload = await response.json();
    if (!response.ok || payload.error) {
      throw new Error(payload.error || "Could not load outputs.");
    }
    state.outputDir = outputDir;
    hydrateFromResultIndex(payload);
    setBusy(false, `Loaded ${payload.runs.length} run(s).`);
  } catch (error) {
    clearSelection();
    setBusy(false, error.message || "Could not load outputs.");
  }
}

function hydrateFromResultIndex(payload) {
  state.runs = payload.runs || [];
  renderRunSelect(state.runs);
  if (!state.runs.length) {
    clearSelection();
    return;
  }
  const preferred = state.selectedLabel && state.runs.find((run) => run.label === state.selectedLabel);
  selectRun(preferred ? preferred.label : state.runs[0].label);
}

function renderRunSelect(runs) {
  elements.runSelect.innerHTML = "";
  if (!runs.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No runs";
    elements.runSelect.appendChild(option);
    return;
  }
  for (const run of runs) {
    const option = document.createElement("option");
    option.value = run.label;
    option.textContent = run.label;
    elements.runSelect.appendChild(option);
  }
}

async function selectRun(label) {
  state.selectedLabel = label;
  elements.runSelect.value = label;

  const run = state.runs.find((item) => item.label === label);
  if (!run) {
    return;
  }

  renderStats(run.summary);
  elements.chartTitle.textContent = label;
  elements.chartMeta.textContent = "Scroll = zoom, drag = pan, double-click = reset, B = buy, S = sell";

  const [equityResponse, fillsResponse] = await Promise.all([
    fetch(`/api/equity?outputDir=${encodeURIComponent(state.outputDir)}&label=${encodeURIComponent(label)}`),
    fetch(`/api/fills?outputDir=${encodeURIComponent(state.outputDir)}&label=${encodeURIComponent(label)}&limit=5000`),
  ]);

  const equityPayload = await equityResponse.json();
  const fillsPayload = await fillsResponse.json();
  if (equityPayload.error || fillsPayload.error) {
    setBusy(false, equityPayload.error || fillsPayload.error);
    return;
  }

  state.chart.points = equityPayload.points;
  state.chart.fills = fillsPayload.fills;
  resetChartView();
}

function renderStats(summary) {
  elements.totalPnl.textContent = formatNumber(summary?.total_pnl);
  elements.realizedPnl.textContent = formatNumber(summary?.realized_pnl);
  elements.unrealizedPnl.textContent = formatNumber(summary?.unrealized_pnl);
  elements.sharpeLike.textContent = formatNumber(summary?.metrics?.sharpe_like);
  elements.maxDrawdown.textContent = formatNumber(summary?.metrics?.max_drawdown);
  elements.fillRatio.textContent = summary ? formatRatio(summary.metrics.fill_ratio) : "-";
}

function drawEquityCurve(points, fills) {
  const canvas = elements.equityCanvas;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, width, height);

  if (!points.length) {
    ctx.fillStyle = "#ffffff";
    ctx.font = "16px Helvetica Neue";
    ctx.fillText("No equity data.", 24, 40);
    return;
  }

  const padX = 24;
  const padY = 24;
  const plotWidth = width - padX * 2;
  const plotHeight = height - padY * 2;
  const values = points.map((point) => point.total_pnl);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const indexByTimestamp = new Map(points.map((point, index) => [point.timestamp, index]));

  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i += 1) {
    const y = padY + (plotHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padX, y);
    ctx.lineTo(width - padX, y);
    ctx.stroke();
  }

  const zeroY = padY + plotHeight - (((0 - min) / span) * plotHeight);
  if (zeroY >= padY && zeroY <= height - padY) {
    ctx.strokeStyle = "rgba(255,255,255,0.35)";
    ctx.beginPath();
    ctx.moveTo(padX, zeroY);
    ctx.lineTo(width - padX, zeroY);
    ctx.stroke();
  }

  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = padX + (index / Math.max(points.length - 1, 1)) * plotWidth;
    const y = padY + plotHeight - (((point.total_pnl - min) / span) * plotHeight);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();

  const markers = groupFillsForMarkers(fills);
  for (const marker of markers) {
    const index = indexByTimestamp.get(marker.timestamp);
    if (index === undefined) {
      continue;
    }
    const point = points[index];
    const x = padX + (index / Math.max(points.length - 1, 1)) * plotWidth;
    const y = padY + plotHeight - (((point.total_pnl - min) / span) * plotHeight);
    drawMarker(ctx, x, y, marker.side);
  }

  ctx.fillStyle = "#ffffff";
  ctx.font = "12px monospace";
  ctx.fillText(`min ${formatNumber(min)}`, padX, height - 8);
  const maxLabel = `max ${formatNumber(max)}`;
  ctx.fillText(maxLabel, width - padX - ctx.measureText(maxLabel).width, 16);
}

function drawCurrentChart() {
  drawEquityCurve(getVisiblePoints(), getVisibleFills());
}

function getVisiblePoints() {
  const points = state.chart.points;
  if (!points.length) {
    return [];
  }
  const start = Math.max(0, Math.floor(state.chart.viewStart));
  const end = Math.min(points.length, Math.ceil(state.chart.viewEnd));
  return points.slice(start, Math.max(start + 1, end));
}

function getVisibleFills() {
  const points = state.chart.points;
  const fills = state.chart.fills;
  if (!points.length || !fills.length) {
    return [];
  }
  const startIndex = Math.max(0, Math.floor(state.chart.viewStart));
  const endIndex = Math.min(points.length - 1, Math.ceil(state.chart.viewEnd) - 1);
  const startTimestamp = points[startIndex].timestamp;
  const endTimestamp = points[endIndex].timestamp;
  return fills.filter((fill) => fill.timestamp >= startTimestamp && fill.timestamp <= endTimestamp);
}

function groupFillsForMarkers(fills) {
  const markers = new Map();
  for (const fill of fills) {
    const side = fill.buyer === "SUBMISSION" ? "BUY" : "SELL";
    const key = `${fill.timestamp}-${side}`;
    if (!markers.has(key)) {
      markers.set(key, { timestamp: fill.timestamp, side });
    }
  }
  return [...markers.values()];
}

function drawMarker(ctx, x, y, side) {
  const markerY = side === "BUY" ? y - 12 : y + 12;
  ctx.save();
  ctx.beginPath();
  ctx.arc(x, markerY, 8, 0, Math.PI * 2);
  if (side === "BUY") {
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.fillStyle = "#000000";
  } else {
    ctx.fillStyle = "#000000";
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
  }
  ctx.font = "10px monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(side === "BUY" ? "B" : "S", x, markerY);
  ctx.restore();
}

function clearSelection() {
  renderStats(null);
  state.chart.points = [];
  state.chart.fills = [];
  state.chart.viewStart = 0;
  state.chart.viewEnd = 1;
  elements.chartTitle.textContent = "Equity Curve";
  elements.chartMeta.textContent = "Scroll = zoom, drag = pan, double-click = reset, B = buy, S = sell";
  drawEquityCurve([], []);
}

function setBusy(isBusy, message) {
  elements.runButton.disabled = isBusy;
  elements.loadButton.disabled = isBusy;
  elements.runSelect.disabled = isBusy;
  elements.status.textContent = message;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function formatRatio(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function resetChartView() {
  const pointCount = state.chart.points.length;
  state.chart.viewStart = 0;
  state.chart.viewEnd = Math.max(1, pointCount);
  drawCurrentChart();
}

function onChartWheel(event) {
  if (!state.chart.points.length) {
    return;
  }
  event.preventDefault();

  const pointCount = state.chart.points.length;
  const currentSpan = state.chart.viewEnd - state.chart.viewStart;
  const minSpan = Math.min(25, pointCount);
  const maxSpan = pointCount;
  const zoomFactor = event.deltaY < 0 ? 0.82 : 1.22;
  const nextSpan = clamp(currentSpan * zoomFactor, minSpan, maxSpan);
  const anchorRatio = getCanvasRelativeX(event);
  const anchorIndex = state.chart.viewStart + currentSpan * anchorRatio;

  let nextStart = anchorIndex - nextSpan * anchorRatio;
  let nextEnd = nextStart + nextSpan;

  if (nextStart < 0) {
    nextStart = 0;
    nextEnd = nextSpan;
  }
  if (nextEnd > pointCount) {
    nextEnd = pointCount;
    nextStart = pointCount - nextSpan;
  }

  state.chart.viewStart = Math.max(0, nextStart);
  state.chart.viewEnd = Math.min(pointCount, nextEnd);
  drawCurrentChart();
}

function onChartMouseDown(event) {
  if (!state.chart.points.length) {
    return;
  }
  state.chart.dragging = true;
  state.chart.lastClientX = event.clientX;
  elements.equityCanvas.classList.add("dragging");
}

function onChartMouseMove(event) {
  if (!state.chart.dragging || !state.chart.points.length) {
    return;
  }
  const rect = elements.equityCanvas.getBoundingClientRect();
  const dx = event.clientX - state.chart.lastClientX;
  state.chart.lastClientX = event.clientX;

  const pointCount = state.chart.points.length;
  const currentSpan = state.chart.viewEnd - state.chart.viewStart;
  const shift = (dx / rect.width) * currentSpan;

  let nextStart = state.chart.viewStart - shift;
  let nextEnd = state.chart.viewEnd - shift;

  if (nextStart < 0) {
    nextStart = 0;
    nextEnd = currentSpan;
  }
  if (nextEnd > pointCount) {
    nextEnd = pointCount;
    nextStart = pointCount - currentSpan;
  }

  state.chart.viewStart = nextStart;
  state.chart.viewEnd = nextEnd;
  drawCurrentChart();
}

function onChartMouseUp() {
  state.chart.dragging = false;
  elements.equityCanvas.classList.remove("dragging");
}

function getCanvasRelativeX(event) {
  const rect = elements.equityCanvas.getBoundingClientRect();
  const x = clamp(event.clientX - rect.left, 0, rect.width);
  return rect.width === 0 ? 0.5 : x / rect.width;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
