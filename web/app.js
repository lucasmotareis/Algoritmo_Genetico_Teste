const form = document.getElementById("runForm");
const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const statusText = document.getElementById("statusText");
const sourceSelect = document.getElementById("sourceSelect");
const runModeSelect = document.getElementById("runModeSelect");

const fields = {
  lastClose: document.getElementById("lastClose"),
  generation: document.getElementById("generation"),
  evaluated: document.getElementById("evaluated"),
  bestFitness: document.getElementById("bestFitness"),
  testReturn: document.getElementById("testReturn"),
  testDrawdown: document.getElementById("testDrawdown"),
  marketRange: document.getElementById("marketRange"),
  runRange: document.getElementById("runRange"),
  testSummary: document.getElementById("testSummary"),
  genesBadge: document.getElementById("genesBadge"),
  genesText: document.getElementById("genesText"),
  generationRows: document.getElementById("generationRows"),
  generationCount: document.getElementById("generationCount"),
  configRows: document.getElementById("configRows"),
  configCount: document.getElementById("configCount"),
  windowRows: document.getElementById("windowRows"),
  windowCount: document.getElementById("windowCount"),
  tradeRows: document.getElementById("tradeRows"),
  tradeCount: document.getElementById("tradeCount"),
};

const charts = {
  price: document.getElementById("priceChart"),
  fitness: document.getElementById("fitnessChart"),
  equity: document.getElementById("equityChart"),
};

let controller = null;
let priceSeries = [];
let fitnessSeries = [];
let equitySeries = [];
let generationsSeen = 0;
let windowsSeen = 0;
let configsSeen = 0;

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPct(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("pt-BR", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setRunning(isRunning) {
  startButton.disabled = isRunning;
  stopButton.disabled = !isRunning;
}

function resetUi() {
  priceSeries = [];
  fitnessSeries = [];
  equitySeries = [];
  generationsSeen = 0;
  windowsSeen = 0;
  configsSeen = 0;
  fields.lastClose.textContent = "-";
  fields.generation.textContent = "0/0";
  fields.evaluated.textContent = "0";
  fields.bestFitness.textContent = "-";
  fields.testReturn.textContent = "-";
  fields.testDrawdown.textContent = "-";
  fields.marketRange.textContent = "-";
  fields.runRange.textContent = "-";
  fields.testSummary.textContent = "-";
  fields.genesBadge.textContent = "-";
  fields.genesText.textContent = "Aguardando execucao.";
  fields.generationRows.innerHTML = "";
  fields.configRows.innerHTML = "";
  fields.windowRows.innerHTML = "";
  fields.tradeRows.innerHTML = "";
  fields.generationCount.textContent = "0 linhas";
  fields.configCount.textContent = "0 configs";
  fields.windowCount.textContent = "0 janelas";
  fields.tradeCount.textContent = "0 trades";
  drawLineChart(charts.price, [], { color: "#345ee8", label: "Aguardando dados" });
  drawLineChart(charts.fitness, [], { color: "#0f766e", label: "Aguardando dados" });
  drawLineChart(charts.equity, [], { color: "#a96812", label: "Aguardando dados" });
}

function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(320, rect.width);
  const height = Math.max(220, rect.height);
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width, height };
}

function drawLineChart(canvas, values, options) {
  const { ctx, width, height } = setupCanvas(canvas);
  const color = options.color || "#345ee8";
  const label = options.label || "";
  const cleanValues = values.filter((value) => Number.isFinite(value));

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcfd";
  ctx.fillRect(0, 0, width, height);

  const pad = { top: 22, right: 24, bottom: 30, left: 52 };
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;

  ctx.strokeStyle = "#e2e8ef";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#64717d";
  ctx.font = "12px Arial";

  for (let i = 0; i <= 4; i += 1) {
    const y = pad.top + (chartHeight * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
  }

  if (cleanValues.length < 2) {
    ctx.fillStyle = "#64717d";
    ctx.fillText(label, pad.left, pad.top + 18);
    return;
  }

  let min = Math.min(...cleanValues);
  let max = Math.max(...cleanValues);
  if (min === max) {
    min -= Math.abs(min || 1) * 0.05;
    max += Math.abs(max || 1) * 0.05;
  }
  const span = max - min;
  const yFor = (value) => pad.top + chartHeight - ((value - min) / span) * chartHeight;
  const xFor = (index) => pad.left + (chartWidth * index) / (cleanValues.length - 1);

  ctx.fillStyle = "#64717d";
  ctx.fillText(formatNumber(max, 2), 8, pad.top + 4);
  ctx.fillText(formatNumber(min, 2), 8, pad.top + chartHeight);

  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  cleanValues.forEach((value, index) => {
    const x = xFor(index);
    const y = yFor(value);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  const lastX = xFor(cleanValues.length - 1);
  const lastY = yFor(cleanValues[cleanValues.length - 1]);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#28323b";
  ctx.font = "700 12px Arial";
  ctx.fillText(label, pad.left, 16);
}

function updateSourceFields() {
  const source = sourceSelect.value;
  form.elements.ticker.disabled = source !== "ticker";
  form.elements.start.disabled = source !== "ticker";
  form.elements.end.disabled = source !== "ticker";
  form.elements.csv.disabled = source !== "csv";
}

function updateModeFields() {
  const isWalkForward = runModeSelect.value === "walk_forward" || runModeSelect.value === "optimize_config";
  const isOptimize = runModeSelect.value === "optimize_config";
  document.querySelectorAll(".simple-option input, .simple-option select").forEach((element) => {
    element.disabled = isWalkForward;
  });
  document.querySelectorAll(".walk-option input, .walk-option select").forEach((element) => {
    element.disabled = !isWalkForward;
  });
  document.querySelectorAll(".optimize-option input, .optimize-option select").forEach((element) => {
    element.disabled = !isOptimize;
  });
}

function buildQuery() {
  const params = new URLSearchParams();
  const data = new FormData(form);
  for (const [key, value] of data.entries()) {
    params.set(key, value);
  }
  params.set("interval", "1d");
  return params;
}

function handleMarket(event) {
  fields.lastClose.textContent = formatCurrency(event.last_close);
  fields.marketRange.textContent = `${event.source} | ${event.first_date} ate ${event.last_date} | ${event.bars} candles`;
  if (event.run_mode === "walk_forward" || event.run_mode === "optimize_config") {
    fields.runRange.textContent = `${event.windows} janelas | ${event.walk_mode} | treino ${event.train_bars} / teste ${event.test_bars} / passo ${event.step_size}`;
    fields.windowCount.textContent = `${event.windows} janelas`;
    if (event.config_trials) fields.configCount.textContent = `${event.config_trials} configs`;
  } else {
    fields.runRange.textContent = `${event.train_bars} treino / ${event.test_bars} teste`;
  }
  priceSeries = event.price_series.map((item) => item.close);
  drawLineChart(charts.price, priceSeries, { color: "#345ee8", label: "Fechamento" });
}

function handleGeneration(event) {
  generationsSeen += 1;
  const totalGenerations = Number(form.elements.generations.value || event.generation);
  const best = event.best;
  const generationBest = event.generation_best;
  const evaluated = event.total_evaluated_individuals || event.evaluated_individuals;
  const generationLabel = event.window ? `J${event.window}/G${event.generation}` : `G${event.generation}`;

  if (event.window) {
    fields.generation.textContent = `J${event.window}/${event.total_windows} G${event.generation}/${totalGenerations}`;
  } else {
    fields.generation.textContent = `${event.generation}/${totalGenerations}`;
  }
  fields.evaluated.textContent = formatNumber(evaluated, 0);
  fields.bestFitness.textContent = formatNumber(best.fitness, 4);
  fields.genesBadge.textContent = generationLabel;
  fields.genesText.textContent = [
    event.best_genes_text,
    event.validation_active ? `gap treino/validacao=${formatPct(event.best_overfit_gap)}` : "validacao interna inativa",
  ].join("\n");

  fitnessSeries.push(best.fitness);
  drawLineChart(charts.fitness, fitnessSeries, { color: "#0f766e", label: "Melhor score" });

  const returnClass = generationBest.total_return >= 0 ? "positive" : "negative";
  fields.generationRows.insertAdjacentHTML(
    "afterbegin",
    `<tr>
      <td>${generationLabel}</td>
      <td>${formatNumber(evaluated, 0)}</td>
      <td>${formatNumber(generationBest.fitness, 4)}</td>
      <td class="${returnClass}">${formatPct(generationBest.total_return)}</td>
      <td>${formatPct(generationBest.max_drawdown)}</td>
      <td>${generationBest.trades}</td>
    </tr>`
  );
  fields.generationCount.textContent = `${generationsSeen} linhas`;
}

function handleWalkWindow(event) {
  statusText.textContent = `Walk-forward janela ${event.window}/${event.total_windows}.`;
  const id = `window-row-${event.window}`;
  const existing = document.getElementById(id);
  if (existing) existing.remove();
  fields.windowRows.insertAdjacentHTML(
    "beforeend",
    `<tr id="${id}">
      <td>${event.window}/${event.total_windows}</td>
      <td>${escapeHtml(event.train_start)}<br>${escapeHtml(event.train_end)}</td>
      <td>${escapeHtml(event.test_start)}<br>${escapeHtml(event.test_end)}</td>
      <td>Executando</td>
      <td>${formatCurrency(event.starting_capital)}</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
    </tr>`
  );
}

function handleWalkWindowResult(event) {
  windowsSeen += 1;
  const item = event.summary;
  const result = item.test_result;
  const row = document.getElementById(`window-row-${event.window}`);
  const returnClass = result.total_return >= 0 ? "positive" : "negative";
  const html = `
    <td>${event.window}/${event.total_windows}</td>
    <td>${escapeHtml(item.train_start)}<br>${escapeHtml(item.train_end)}</td>
    <td>${escapeHtml(item.test_start)}<br>${escapeHtml(item.test_end)}</td>
    <td class="${returnClass}">${formatPct(result.total_return)}</td>
    <td>${formatCurrency(item.ending_capital)}</td>
    <td>${formatPct(result.max_drawdown)}</td>
    <td>${result.trades}</td>
    <td>${formatPct(result.buy_and_hold_return)}</td>`;
  if (row) {
    row.innerHTML = html;
  } else {
    fields.windowRows.insertAdjacentHTML("beforeend", `<tr id="window-row-${event.window}">${html}</tr>`);
  }
  fields.windowCount.textContent = `${windowsSeen}/${event.total_windows} janelas`;

  equitySeries.push(...event.window_series.map((point) => point.equity));
  drawLineChart(charts.equity, equitySeries, { color: "#a96812", label: "Capital OOS" });
}

function configParamsText(config) {
  const maxTrades = config.max_trades === null || config.max_trades === undefined ? "sem limite" : config.max_trades;
  return [
    `pop=${config.population}`,
    `gen=${config.generations}`,
    `mut=${formatNumber(config.mutation_rate, 2)}`,
    `valid=${formatNumber(config.validation_ratio, 2)}`,
    `peso=${formatNumber(config.validation_weight, 2)}`,
    `overfit=${formatNumber(config.overfit_penalty, 2)}`,
    `min=${config.min_trades}`,
    `max=${maxTrades}`,
  ].join(" | ");
}

function handleConfigStart(event) {
  statusText.textContent = `Testando configuracao ${event.config_number}/${event.total_configs}.`;
  const id = `config-row-${event.config_number}`;
  const existing = document.getElementById(id);
  if (existing) existing.remove();
  fields.configRows.insertAdjacentHTML(
    "beforeend",
    `<tr id="${id}">
      <td>${event.config_number}/${event.total_configs}<br>${escapeHtml(event.config.name)}</td>
      <td>Executando</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
      <td>-</td>
      <td>${escapeHtml(configParamsText(event.config))}</td>
    </tr>`
  );
}

function handleConfigResult(event) {
  configsSeen += 1;
  const item = event.result;
  const summary = item.summary;
  const config = item.config;
  const id = `config-row-${event.config_number}`;
  const row = document.getElementById(id);
  const scoreClass = summary.robust_score >= 0 ? "positive" : "negative";
  const returnClass = summary.total_return >= 0 ? "positive" : "negative";
  const versusClass = summary.return_vs_buy_hold >= 0 ? "positive" : "negative";
  const html = `
    <td>${event.config_number}/${event.total_configs}<br>${escapeHtml(config.name)}</td>
    <td class="${scoreClass}">${formatNumber(summary.robust_score, 4)}</td>
    <td class="${returnClass}">${formatPct(summary.total_return)}</td>
    <td>${formatPct(summary.max_drawdown)}</td>
    <td>${formatPct(summary.buy_and_hold_return)}</td>
    <td class="${versusClass}">${formatPct(summary.return_vs_buy_hold)}</td>
    <td>${summary.positive_windows}/${summary.windows}</td>
    <td>${summary.trades}</td>
    <td>${escapeHtml(summary.classification)}</td>
    <td>${escapeHtml(configParamsText(config))}</td>`;
  if (row) {
    row.innerHTML = html;
  } else {
    fields.configRows.insertAdjacentHTML("beforeend", `<tr id="${id}">${html}</tr>`);
  }
  fields.configCount.textContent = `${configsSeen}/${event.total_configs} configs`;
  fields.bestFitness.textContent = formatNumber(summary.robust_score, 4);
  fitnessSeries.push(summary.robust_score);
  drawLineChart(charts.fitness, fitnessSeries, { color: "#0f766e", label: "Score robusto" });
}

function renderTrades(trades) {
  if (!trades.length) {
    fields.tradeRows.innerHTML = '<tr><td colspan="5">Sem trades fora da amostra.</td></tr>';
  } else {
    fields.tradeRows.innerHTML = trades
      .map((trade) => {
        const returnClass = trade.return_pct >= 0 ? "positive" : "negative";
        const windowText = trade.window ? `J${trade.window} ` : "";
        return `<tr>
          <td>${windowText}${escapeHtml(trade.entry_date)}</td>
          <td>${escapeHtml(trade.exit_date)}</td>
          <td class="${returnClass}">${formatPct(trade.return_pct)}</td>
          <td>${trade.hold_days}</td>
          <td>${escapeHtml(trade.exit_reason)}</td>
        </tr>`;
      })
      .join("");
  }
  fields.tradeCount.textContent = `${trades.length} trades`;
}

function handleComplete(event) {
  const test = event.test_result;
  const train = event.train_result;
  fields.testReturn.textContent = formatPct(test.total_return);
  fields.testDrawdown.textContent = formatPct(test.max_drawdown);
  fields.testSummary.textContent = `Treino ${formatPct(train.total_return)} | Teste ${formatPct(test.total_return)} | Buy hold ${formatPct(test.buy_and_hold_return)}`;
  fields.genesBadge.textContent = `${event.trades.length} trades`;
  fields.genesText.textContent = event.best_genes_text;

  equitySeries = event.test_series.map((item) => item.equity);
  drawLineChart(charts.equity, equitySeries, { color: "#a96812", label: "Capital OOS" });
  renderTrades(event.trades);
}

function handleWalkComplete(event) {
  const summary = event.summary;
  fields.testReturn.textContent = formatPct(summary.total_return);
  fields.testDrawdown.textContent = formatPct(summary.max_drawdown);
  fields.bestFitness.textContent = formatNumber(summary.robust_score, 4);
  fields.testSummary.textContent = `OOS ${event.period_start} ate ${event.period_end} | Buy hold ${formatPct(summary.buy_and_hold_return)} | ${summary.positive_windows}/${summary.windows} janelas positivas | ${summary.classification}`;
  fields.genesBadge.textContent = `${summary.windows} janelas`;
  fields.generation.textContent = `${summary.windows}/${summary.windows}`;
  fields.evaluated.textContent = formatNumber(Number(form.elements.population.value) * Number(form.elements.generations.value) * summary.windows, 0);

  fields.genesText.textContent = event.windows
    .map((item) => {
      const result = item.test_result;
      const trainResult = item.train_result;
      return [
        `Janela ${item.window}: ${item.test_start} ate ${item.test_end}`,
        `treino=${formatPct(trainResult.total_return)} | OOS=${formatPct(result.total_return)} | drawdown=${formatPct(result.max_drawdown)} | trades=${result.trades}`,
        item.best_genes_text,
      ].join("\n");
    })
    .join("\n\n");

  equitySeries = event.test_series.map((item) => item.equity);
  drawLineChart(charts.equity, equitySeries, { color: "#a96812", label: "Capital OOS" });
  renderTrades(event.trades);
}

function handleConfigComplete(event) {
  const best = event.best;
  const summary = best.summary;
  document.querySelectorAll(".best-row").forEach((row) => row.classList.remove("best-row"));
  const bestRow = document.getElementById(`config-row-${event.best_config_number}`);
  if (bestRow) bestRow.classList.add("best-row");
  fields.testReturn.textContent = formatPct(summary.total_return);
  fields.testDrawdown.textContent = formatPct(summary.max_drawdown);
  fields.bestFitness.textContent = formatNumber(summary.robust_score, 4);
  fields.testSummary.textContent = `Melhor config ${event.best_config_number} | ${summary.classification} | vs B&H ${formatPct(summary.return_vs_buy_hold)} | ${summary.positive_windows}/${summary.windows} janelas positivas`;
  fields.genesBadge.textContent = `Config ${event.best_config_number}`;
  fields.generation.textContent = `${event.results.length}/${event.results.length}`;
  fields.evaluated.textContent = formatNumber(
    event.results.reduce((total, item) => total + (item.config.population * item.config.generations * summary.windows), 0),
    0
  );

  fields.genesText.textContent = [
    `Melhor configuracao: ${best.config.name}`,
    `score=${formatNumber(summary.robust_score, 4)} | OOS=${formatPct(summary.total_return)} | drawdown=${formatPct(summary.max_drawdown)} | vs buy hold=${formatPct(summary.return_vs_buy_hold)}`,
    configParamsText(best.config),
    "",
    ...best.windows.map((item) => {
      const result = item.test_result;
      return `Janela ${item.window}: OOS=${formatPct(result.total_return)} | drawdown=${formatPct(result.max_drawdown)} | trades=${result.trades}`;
    }),
  ].join("\n");

  equitySeries = best.test_series.map((item) => item.equity);
  drawLineChart(charts.equity, equitySeries, { color: "#a96812", label: "Capital OOS" });
  renderTrades(best.trades);
}

function handleEvent(event) {
  if (event.type === "status") {
    statusText.textContent = event.message;
  } else if (event.type === "market") {
    statusText.textContent = "Dados carregados.";
    handleMarket(event);
  } else if (event.type === "generation") {
    statusText.textContent = event.window
      ? `Janela ${event.window}/${event.total_windows}, geracao ${event.generation}.`
      : `Geracao ${event.generation} avaliada.`;
    handleGeneration(event);
  } else if (event.type === "walk_window") {
    handleWalkWindow(event);
  } else if (event.type === "walk_window_result") {
    handleWalkWindowResult(event);
  } else if (event.type === "config_start") {
    handleConfigStart(event);
  } else if (event.type === "config_result") {
    handleConfigResult(event);
  } else if (event.type === "complete") {
    statusText.textContent = "Execucao finalizada.";
    handleComplete(event);
  } else if (event.type === "walk_complete") {
    statusText.textContent = "Walk-forward finalizado.";
    handleWalkComplete(event);
  } else if (event.type === "config_complete") {
    statusText.textContent = "Otimizacao de configuracao finalizada.";
    handleConfigComplete(event);
  } else if (event.type === "error") {
    statusText.textContent = event.message;
    setRunning(false);
  }
}

async function runAlgorithm() {
  resetUi();
  setRunning(true);
  statusText.textContent = "Iniciando.";
  controller = new AbortController();

  try {
    const response = await fetch(`/api/run?${buildQuery().toString()}`, {
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok || !response.body) {
      throw new Error(`Falha HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        handleEvent(JSON.parse(line));
      }
    }
  } catch (error) {
    if (error.name === "AbortError") {
      statusText.textContent = "Execucao interrompida.";
    } else {
      statusText.textContent = error.message;
    }
  } finally {
    setRunning(false);
    controller = null;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runAlgorithm();
});

stopButton.addEventListener("click", () => {
  if (controller) controller.abort();
});

sourceSelect.addEventListener("change", updateSourceFields);
runModeSelect.addEventListener("change", updateModeFields);

window.addEventListener("resize", () => {
  drawLineChart(charts.price, priceSeries, { color: "#345ee8", label: "Fechamento" });
  drawLineChart(charts.fitness, fitnessSeries, { color: "#0f766e", label: "Melhor score" });
  drawLineChart(charts.equity, equitySeries, { color: "#a96812", label: "Capital OOS" });
});

updateSourceFields();
updateModeFields();
resetUi();
