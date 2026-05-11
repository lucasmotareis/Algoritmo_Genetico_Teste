from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen


TRADING_DAYS = 252


@dataclass(frozen=True)
class PriceBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Genes:
    trade_mode: int
    sma_short: int
    sma_long: int
    rsi_period: int
    rsi_entry: float
    rsi_exit: float
    ema_short: int
    ema_long: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    atr_period: int
    atr_stop_mult: float
    atr_take_mult: float
    min_entry_signals: int
    min_exit_signals: int
    stop_loss: float
    take_profit: float
    max_hold_days: int


@dataclass
class Trade:
    side: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    return_pct: float
    hold_days: int
    exit_reason: str


@dataclass
class BacktestResult:
    final_equity: float
    total_return: float
    annual_return: float
    max_drawdown: float
    trades: int
    long_trades: int
    short_trades: int
    win_rate: float
    profit_factor: float
    average_trade_return: float
    best_trade_return: float
    worst_trade_return: float
    exposure: float
    buy_and_hold_return: float
    return_vs_buy_hold: float
    return_drawdown_ratio: float
    trades_per_year: float
    consistency_score: float
    fitness: float
    trade_log: list[Trade]
    equity_curve: list[float]


def parse_float(value: str) -> float | None:
    value = value.strip()
    if not value or value.lower() in {"null", "nan"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_yahoo_csv(path: Path) -> list[PriceBar]:
    bars: list[PriceBar] = []
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"Date", "Open", "High", "Low", "Close"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV sem colunas obrigatorias: {', '.join(sorted(missing))}")

        for row in reader:
            open_price = parse_float(row.get("Open", ""))
            high = parse_float(row.get("High", ""))
            low = parse_float(row.get("Low", ""))
            close = parse_float(row.get("Close", ""))
            volume = parse_float(row.get("Volume", "")) or 0.0
            if None in {open_price, high, low, close}:
                continue
            bars.append(
                PriceBar(
                    date=row["Date"],
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )

    if len(bars) < 250:
        raise ValueError("Poucos dados no CSV. Use pelo menos 250 candles diarios.")
    return bars


def download_yahoo_history(ticker: str, start: str, end: str, interval: str) -> list[PriceBar]:
    start_ts = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp())
    encoded_ticker = quote(ticker, safe="")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_ticker}"
        f"?period1={start_ts}&period2={end_ts}&interval={interval}"
        "&events=history&includeAdjustedClose=true"
    )

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    chart = payload.get("chart", {})
    if chart.get("error"):
        raise ValueError(f"Erro do Yahoo Finance: {chart['error']}")

    results = chart.get("result") or []
    if not results:
        raise ValueError("Yahoo Finance nao retornou resultados.")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = (result.get("indicators", {}).get("quote") or [{}])[0]
    opens = quotes.get("open") or []
    highs = quotes.get("high") or []
    lows = quotes.get("low") or []
    closes = quotes.get("close") or []
    volumes = quotes.get("volume") or []

    bars: list[PriceBar] = []
    for i, timestamp in enumerate(timestamps):
        values = [
            opens[i] if i < len(opens) else None,
            highs[i] if i < len(highs) else None,
            lows[i] if i < len(lows) else None,
            closes[i] if i < len(closes) else None,
        ]
        if any(value is None for value in values):
            continue
        volume = volumes[i] if i < len(volumes) and volumes[i] is not None else 0.0
        bars.append(
            PriceBar(
                date=datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat(),
                open=float(values[0]),
                high=float(values[1]),
                low=float(values[2]),
                close=float(values[3]),
                volume=float(volume),
            )
        )

    if len(bars) < 250:
        raise ValueError("Poucos dados retornados pelo Yahoo. Use um periodo maior.")
    return bars


def generate_demo_gold_like_data(days: int, seed: int) -> list[PriceBar]:
    rng = random.Random(seed)
    price = 1850.0
    bars: list[PriceBar] = []
    for day in range(days):
        drift = 0.00015
        cycle = 0.0025 * math.sin(day / 37.0)
        noise = rng.gauss(0.0, 0.008)
        daily_return = drift + cycle + noise
        open_price = price
        close = max(100.0, open_price * (1.0 + daily_return))
        high = max(open_price, close) * (1.0 + abs(rng.gauss(0.002, 0.002)))
        low = min(open_price, close) * (1.0 - abs(rng.gauss(0.002, 0.002)))
        volume = 100_000 + rng.randint(0, 50_000)
        bars.append(
            PriceBar(
                date=f"demo-{day + 1:04d}",
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=float(volume),
            )
        )
        price = close
    return bars


def simple_moving_average(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    rolling_sum = 0.0
    for i, value in enumerate(values):
        rolling_sum += value
        if i >= window:
            rolling_sum -= values[i - window]
        if i >= window - 1:
            result[i] = rolling_sum / window
    return result


def exponential_moving_average(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < window:
        return result

    multiplier = 2.0 / (window + 1)
    ema = sum(values[:window]) / window
    result[window - 1] = ema
    for i in range(window, len(values)):
        ema = ((values[i] - ema) * multiplier) + ema
        result[i] = ema
    return result


def exponential_moving_average_nullable(values: list[float | None], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    multiplier = 2.0 / (window + 1)
    seed_values: list[float] = []
    ema: float | None = None

    for i, value in enumerate(values):
        if value is None:
            continue
        if ema is None:
            seed_values.append(value)
            if len(seed_values) == window:
                ema = sum(seed_values) / window
                result[i] = ema
            continue
        ema = ((value - ema) * multiplier) + ema
        result[i] = ema
    return result


def macd(
    values: list[float],
    fast_window: int,
    slow_window: int,
    signal_window: int,
) -> tuple[list[float | None], list[float | None]]:
    fast = exponential_moving_average(values, fast_window)
    slow = exponential_moving_average(values, slow_window)
    line: list[float | None] = []
    for fast_value, slow_value in zip(fast, slow):
        if fast_value is None or slow_value is None:
            line.append(None)
        else:
            line.append(fast_value - slow_value)
    signal = exponential_moving_average_nullable(line, signal_window)
    return line, signal


def average_true_range(bars: list[PriceBar], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(bars)
    if len(bars) < window + 1:
        return result

    true_ranges: list[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            true_ranges.append(bar.high - bar.low)
        else:
            previous_close = bars[i - 1].close
            true_ranges.append(
                max(
                    bar.high - bar.low,
                    abs(bar.high - previous_close),
                    abs(bar.low - previous_close),
                )
            )

    atr = sum(true_ranges[1 : window + 1]) / window
    result[window] = atr
    for i in range(window + 1, len(bars)):
        atr = ((atr * (window - 1)) + true_ranges[i]) / window
        result[i] = atr
    return result


def rsi(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    gains: list[float] = [0.0]
    losses: list[float] = [0.0]

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains[1 : window + 1]) / window
    avg_loss = sum(losses[1 : window + 1]) / window
    if avg_loss == 0:
        result[window] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[window] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(window + 1, len(values)):
        avg_gain = ((avg_gain * (window - 1)) + gains[i]) / window
        avg_loss = ((avg_loss * (window - 1)) + losses[i]) / window
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))

    return result


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_genes(genes: Genes) -> Genes:
    trade_mode = int(clamp(round(genes.trade_mode), 0, 1))
    sma_short = int(clamp(round(genes.sma_short), 3, 60))
    sma_long = int(clamp(round(genes.sma_long), sma_short + 5, 220))
    rsi_period = int(clamp(round(genes.rsi_period), 5, 40))
    rsi_entry = clamp(genes.rsi_entry, 20.0, 75.0)
    rsi_exit = clamp(genes.rsi_exit, rsi_entry + 5.0, 95.0)
    ema_short = int(clamp(round(genes.ema_short), 3, 80))
    ema_long = int(clamp(round(genes.ema_long), ema_short + 5, 240))
    macd_fast = int(clamp(round(genes.macd_fast), 3, 30))
    macd_slow = int(clamp(round(genes.macd_slow), macd_fast + 5, 90))
    macd_signal = int(clamp(round(genes.macd_signal), 3, 30))
    atr_period = int(clamp(round(genes.atr_period), 5, 40))
    atr_stop_mult = clamp(genes.atr_stop_mult, 0.5, 5.0)
    atr_take_mult = clamp(genes.atr_take_mult, 0.5, 8.0)
    min_entry_signals = int(clamp(round(genes.min_entry_signals), 1, 4))
    min_exit_signals = int(clamp(round(genes.min_exit_signals), 1, 4))
    stop_loss = clamp(genes.stop_loss, 0.003, 0.12)
    take_profit = clamp(genes.take_profit, 0.005, 0.25)
    max_hold_days = int(clamp(round(genes.max_hold_days), 2, 90))
    return Genes(
        trade_mode=trade_mode,
        sma_short=sma_short,
        sma_long=sma_long,
        rsi_period=rsi_period,
        rsi_entry=rsi_entry,
        rsi_exit=rsi_exit,
        ema_short=ema_short,
        ema_long=ema_long,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        atr_period=atr_period,
        atr_stop_mult=atr_stop_mult,
        atr_take_mult=atr_take_mult,
        min_entry_signals=min_entry_signals,
        min_exit_signals=min_exit_signals,
        stop_loss=stop_loss,
        take_profit=take_profit,
        max_hold_days=max_hold_days,
    )


def random_genes(rng: random.Random) -> Genes:
    sma_short = rng.randint(3, 45)
    sma_long = rng.randint(sma_short + 5, 180)
    rsi_entry = rng.uniform(25.0, 70.0)
    rsi_exit = rng.uniform(rsi_entry + 5.0, 90.0)
    ema_short = rng.randint(3, 55)
    ema_long = rng.randint(ema_short + 5, 190)
    macd_fast = rng.randint(3, 22)
    macd_slow = rng.randint(macd_fast + 5, 70)
    return normalize_genes(
        Genes(
            trade_mode=rng.choice([0, 1]),
            sma_short=sma_short,
            sma_long=sma_long,
            rsi_period=rng.randint(5, 30),
            rsi_entry=rsi_entry,
            rsi_exit=rsi_exit,
            ema_short=ema_short,
            ema_long=ema_long,
            macd_fast=macd_fast,
            macd_slow=macd_slow,
            macd_signal=rng.randint(3, 20),
            atr_period=rng.randint(5, 30),
            atr_stop_mult=rng.uniform(0.8, 4.0),
            atr_take_mult=rng.uniform(1.0, 6.0),
            min_entry_signals=rng.randint(1, 3),
            min_exit_signals=rng.randint(1, 3),
            stop_loss=rng.uniform(0.006, 0.08),
            take_profit=rng.uniform(0.01, 0.18),
            max_hold_days=rng.randint(3, 60),
        )
    )


def mutate_gene(value: float, scale: float, rng: random.Random) -> float:
    return value + rng.gauss(0.0, scale)


def mutate(genes: Genes, rng: random.Random, probability: float) -> Genes:
    values = genes.__dict__.copy()
    if rng.random() < probability:
        values["sma_short"] = mutate_gene(values["sma_short"], 5.0, rng)
    if rng.random() < probability:
        values["sma_long"] = mutate_gene(values["sma_long"], 12.0, rng)
    if rng.random() < probability:
        values["rsi_period"] = mutate_gene(values["rsi_period"], 3.0, rng)
    if rng.random() < probability:
        values["rsi_entry"] = mutate_gene(values["rsi_entry"], 6.0, rng)
    if rng.random() < probability:
        values["rsi_exit"] = mutate_gene(values["rsi_exit"], 6.0, rng)
    if rng.random() < probability:
        values["ema_short"] = mutate_gene(values["ema_short"], 6.0, rng)
    if rng.random() < probability:
        values["ema_long"] = mutate_gene(values["ema_long"], 14.0, rng)
    if rng.random() < probability:
        values["macd_fast"] = mutate_gene(values["macd_fast"], 4.0, rng)
    if rng.random() < probability:
        values["macd_slow"] = mutate_gene(values["macd_slow"], 8.0, rng)
    if rng.random() < probability:
        values["macd_signal"] = mutate_gene(values["macd_signal"], 3.0, rng)
    if rng.random() < probability:
        values["atr_period"] = mutate_gene(values["atr_period"], 4.0, rng)
    if rng.random() < probability:
        values["atr_stop_mult"] = mutate_gene(values["atr_stop_mult"], 0.4, rng)
    if rng.random() < probability:
        values["atr_take_mult"] = mutate_gene(values["atr_take_mult"], 0.7, rng)
    if rng.random() < probability:
        values["min_entry_signals"] = mutate_gene(values["min_entry_signals"], 1.0, rng)
    if rng.random() < probability:
        values["min_exit_signals"] = mutate_gene(values["min_exit_signals"], 1.0, rng)
    if rng.random() < probability:
        values["stop_loss"] = mutate_gene(values["stop_loss"], 0.01, rng)
    if rng.random() < probability:
        values["take_profit"] = mutate_gene(values["take_profit"], 0.02, rng)
    if rng.random() < probability:
        values["max_hold_days"] = mutate_gene(values["max_hold_days"], 8.0, rng)
    return normalize_genes(Genes(**values))


def crossover(parent_a: Genes, parent_b: Genes, rng: random.Random) -> Genes:
    child_values = {}
    for key in parent_a.__dict__:
        child_values[key] = getattr(parent_a, key) if rng.random() < 0.5 else getattr(parent_b, key)
    return normalize_genes(Genes(**child_values))


def backtest(
    bars: list[PriceBar],
    genes: Genes,
    initial_capital: float,
    transaction_cost: float,
    drawdown_penalty: float,
    trade_penalty: float,
    trade_start_index: int = 0,
    min_trades: int = 1,
    max_trades: int | None = None,
    excess_trade_penalty: float = 0.002,
    benchmark_weight: float = 0.35,
) -> BacktestResult:
    if trade_start_index < 0 or trade_start_index >= len(bars):
        raise ValueError("trade_start_index fora do intervalo de barras.")

    closes = [bar.close for bar in bars]
    sma_short = simple_moving_average(closes, genes.sma_short)
    sma_long = simple_moving_average(closes, genes.sma_long)
    rsi_values = rsi(closes, genes.rsi_period)
    ema_short = exponential_moving_average(closes, genes.ema_short)
    ema_long = exponential_moving_average(closes, genes.ema_long)
    macd_line, macd_signal = macd(closes, genes.macd_fast, genes.macd_slow, genes.macd_signal)
    atr_values = average_true_range(bars, genes.atr_period)

    cash = initial_capital
    units = 0.0
    position_side = 0
    position_capital = 0.0
    entry_price = 0.0
    entry_atr = 0.0
    entry_index = 0
    entry_date = ""
    days_in_market = 0
    trades: list[Trade] = []
    equity_curve: list[float] = []

    def position_equity(price: float) -> float:
        if position_side == 1:
            return units * price
        if position_side == -1 and entry_price > 0.0:
            return max(0.0, position_capital * (2.0 - (price / entry_price)))
        return cash

    def open_position(side: int, bar: PriceBar, atr_value: float, index: int) -> None:
        nonlocal cash, units, position_side, position_capital, entry_price, entry_atr, entry_index, entry_date
        position_capital = cash * (1.0 - transaction_cost)
        units = position_capital / bar.close
        cash = 0.0
        position_side = side
        entry_price = bar.close
        entry_atr = atr_value
        entry_index = index
        entry_date = bar.date

    def close_position(bar: PriceBar, index: int, exit_reason: str) -> None:
        nonlocal cash, units, position_side, position_capital, entry_price, entry_atr, entry_date
        exit_equity = position_equity(bar.close)
        cash = exit_equity * (1.0 - transaction_cost)
        trade_return = (cash / position_capital) - 1.0 if position_capital > 0.0 else 0.0
        trades.append(
            Trade(
                side="long" if position_side == 1 else "short",
                entry_date=entry_date,
                exit_date=bar.date,
                entry_price=entry_price,
                exit_price=bar.close,
                return_pct=trade_return,
                hold_days=index - entry_index,
                exit_reason=exit_reason,
            )
        )
        units = 0.0
        position_side = 0
        position_capital = 0.0
        entry_price = 0.0
        entry_atr = 0.0
        entry_date = ""

    indicator_start_index = max(
        genes.sma_long,
        genes.rsi_period,
        genes.ema_long,
        genes.macd_slow + genes.macd_signal,
        genes.atr_period,
    ) + 1
    start_index = max(indicator_start_index, trade_start_index)
    for i, bar in enumerate(bars):
        price = bar.close
        has_position = position_side != 0

        if i >= start_index:
            short_value = sma_short[i]
            long_value = sma_long[i]
            rsi_value = rsi_values[i]
            ema_short_value = ema_short[i]
            ema_long_value = ema_long[i]
            macd_value = macd_line[i]
            macd_signal_value = macd_signal[i]
            atr_value = atr_values[i]
            if (
                short_value is not None
                and long_value is not None
                and rsi_value is not None
                and ema_short_value is not None
                and ema_long_value is not None
                and macd_value is not None
                and macd_signal_value is not None
                and atr_value is not None
            ):
                bullish_signals = sum(
                    [
                        short_value > long_value,
                        rsi_value <= genes.rsi_entry,
                        ema_short_value > ema_long_value,
                        macd_value > macd_signal_value,
                    ]
                )
                bearish_signals = sum(
                    [
                        short_value < long_value,
                        rsi_value >= genes.rsi_exit,
                        ema_short_value < ema_long_value,
                        macd_value < macd_signal_value,
                    ]
                )
                if has_position:
                    days_in_market += 1
                    current_return = position_side * ((price / entry_price) - 1.0)
                    atr_stop = (entry_atr * genes.atr_stop_mult) / entry_price if entry_atr > 0 else genes.stop_loss
                    atr_take = (entry_atr * genes.atr_take_mult) / entry_price if entry_atr > 0 else genes.take_profit
                    effective_stop = min(genes.stop_loss, atr_stop)
                    effective_take = min(genes.take_profit, atr_take)
                    exit_reason = ""
                    if current_return <= -effective_stop:
                        exit_reason = "stop_loss"
                    elif current_return >= effective_take:
                        exit_reason = "take_profit"
                    elif i - entry_index >= genes.max_hold_days:
                        exit_reason = "max_hold_days"
                    elif position_side == 1 and bearish_signals >= genes.min_exit_signals:
                        exit_reason = "signal_exit"
                    elif position_side == -1 and bullish_signals >= genes.min_exit_signals:
                        exit_reason = "signal_exit"

                    if exit_reason:
                        close_position(bar, i, exit_reason)
                else:
                    should_enter_long = bullish_signals >= genes.min_entry_signals and bullish_signals > bearish_signals
                    should_enter_short = (
                        genes.trade_mode == 1
                        and bearish_signals >= genes.min_entry_signals
                        and bearish_signals > bullish_signals
                    )
                    if should_enter_long:
                        open_position(1, bar, atr_value, i)
                    elif should_enter_short:
                        open_position(-1, bar, atr_value, i)

        equity = position_equity(price) if position_side != 0 else cash
        equity_curve.append(equity)

    if position_side != 0:
        final_bar = bars[-1]
        close_position(final_bar, len(bars) - 1, "end_of_data")
        equity_curve[-1] = cash

    metric_equity_curve = equity_curve[trade_start_index:]
    metric_bars = bars[trade_start_index:]
    final_equity = metric_equity_curve[-1]
    total_return = (final_equity / initial_capital) - 1.0
    years = max(len(metric_bars) / TRADING_DAYS, 1.0 / TRADING_DAYS)
    annual_return = (final_equity / initial_capital) ** (1.0 / years) - 1.0
    max_drawdown = calculate_max_drawdown(metric_equity_curve)
    wins = sum(1 for trade in trades if trade.return_pct > 0.0)
    long_trades = sum(1 for trade in trades if trade.side == "long")
    short_trades = sum(1 for trade in trades if trade.side == "short")
    win_rate = wins / len(trades) if trades else 0.0
    positive_returns = [trade.return_pct for trade in trades if trade.return_pct > 0.0]
    negative_returns = [trade.return_pct for trade in trades if trade.return_pct < 0.0]
    gross_profit = sum(positive_returns)
    gross_loss = abs(sum(negative_returns))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    average_trade_return = sum(trade.return_pct for trade in trades) / len(trades) if trades else 0.0
    best_trade_return = max((trade.return_pct for trade in trades), default=0.0)
    worst_trade_return = min((trade.return_pct for trade in trades), default=0.0)
    exposure = days_in_market / len(metric_bars)
    buy_and_hold_return = (bars[-1].close / bars[trade_start_index].close) - 1.0
    return_vs_buy_hold = total_return - buy_and_hold_return
    return_drawdown_ratio = total_return / max(max_drawdown, 0.001)
    trades_per_year = len(trades) / years
    consistency_score = win_rate if trades else 0.0

    min_trades = max(0, min_trades)
    benchmark_weight = max(0.0, benchmark_weight)
    excess_trades = max(0, len(trades) - max_trades) if max_trades is not None and max_trades > 0 else 0
    missing_trades = max(0, min_trades - len(trades))
    if missing_trades:
        fitness = -1.0 - (0.05 * missing_trades)
    else:
        fitness = (
            total_return
            + (benchmark_weight * return_vs_buy_hold)
            - (drawdown_penalty * max_drawdown)
            - (trade_penalty * len(trades))
            - (excess_trade_penalty * excess_trades)
        )

    return BacktestResult(
        final_equity=final_equity,
        total_return=total_return,
        annual_return=annual_return,
        max_drawdown=max_drawdown,
        trades=len(trades),
        long_trades=long_trades,
        short_trades=short_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        average_trade_return=average_trade_return,
        best_trade_return=best_trade_return,
        worst_trade_return=worst_trade_return,
        exposure=exposure,
        buy_and_hold_return=buy_and_hold_return,
        return_vs_buy_hold=return_vs_buy_hold,
        return_drawdown_ratio=return_drawdown_ratio,
        trades_per_year=trades_per_year,
        consistency_score=consistency_score,
        fitness=fitness,
        trade_log=trades,
        equity_curve=metric_equity_curve,
    )


def calculate_max_drawdown(equity_curve: Iterable[float]) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown


def validation_start_index(total_bars: int, validation_ratio: float) -> int | None:
    if validation_ratio <= 0:
        return None
    validation_size = max(20, int(total_bars * validation_ratio))
    optimization_size = total_bars - validation_size
    if optimization_size < 250 or validation_size < 20:
        return None
    return optimization_size


def robust_fitness(
    optimization_result: BacktestResult,
    validation_result: BacktestResult,
    validation_weight: float,
    overfit_penalty: float,
    consistency_bonus: float = 0.03,
) -> tuple[float, float]:
    validation_weight = clamp(validation_weight, 0.0, 1.0)
    overfit_gap = max(0.0, optimization_result.total_return - validation_result.total_return)
    train_support = min(optimization_result.fitness, validation_result.fitness)
    score = (
        (validation_weight * validation_result.fitness)
        + ((1.0 - validation_weight) * train_support)
        - (overfit_penalty * overfit_gap)
        + (consistency_bonus * validation_result.consistency_score)
    )
    return score, overfit_gap


def robust_walk_forward_metrics(
    total_return: float,
    buy_and_hold_return: float,
    max_drawdown: float,
    total_trades: int,
    years: float,
    positive_windows: int,
    total_windows: int,
    average_train_return: float | None = None,
) -> dict[str, float | str]:
    consistency_score = positive_windows / total_windows if total_windows else 0.0
    return_vs_buy_hold = total_return - buy_and_hold_return
    return_drawdown_ratio = total_return / max(max_drawdown, 0.001)
    trades_per_year = total_trades / max(years, 1.0 / TRADING_DAYS)
    overfit_gap = max(0.0, (average_train_return or 0.0) - total_return)
    trade_load_penalty = min(0.10, total_trades * 0.0002)
    robust_score = (
        total_return
        - (1.5 * max_drawdown)
        + (0.10 * consistency_score)
        + (0.35 * return_vs_buy_hold)
        - trade_load_penalty
        - (0.50 * overfit_gap)
    )

    if return_vs_buy_hold < -0.05:
        label = "fraca contra buy and hold"
    elif overfit_gap > 0.20 and consistency_score < 0.67:
        label = "provavel overfitting"
    elif consistency_score < 0.5 or max_drawdown > 0.15:
        label = "instavel"
    elif total_return > 0.0 and consistency_score >= 0.6:
        label = "boa"
    else:
        label = "instavel"

    return {
        "return_vs_buy_hold": return_vs_buy_hold,
        "return_drawdown_ratio": return_drawdown_ratio,
        "trades_per_year": trades_per_year,
        "consistency_score": consistency_score,
        "overfit_gap": overfit_gap,
        "robust_score": robust_score,
        "classification": label,
    }


def tournament_selection(
    population: list[Genes],
    scores: dict[Genes, BacktestResult],
    rng: random.Random,
    tournament_size: int,
) -> Genes:
    candidates = rng.sample(population, k=min(tournament_size, len(population)))
    return max(candidates, key=lambda genes: scores[genes].fitness)


def evolve(
    train_bars: list[PriceBar],
    population_size: int,
    generations: int,
    mutation_rate: float,
    elite_size: int,
    seed: int,
    initial_capital: float,
    transaction_cost: float,
    drawdown_penalty: float,
    trade_penalty: float,
    verbose: bool = True,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
    validation_ratio: float = 0.2,
    validation_weight: float = 0.65,
    overfit_penalty: float = 1.0,
    min_trades: int = 1,
    max_trades: int | None = None,
    excess_trade_penalty: float = 0.002,
    benchmark_weight: float = 0.35,
) -> tuple[Genes, BacktestResult]:
    rng = random.Random(seed)
    population = [random_genes(rng) for _ in range(population_size)]
    elite_size = max(1, min(elite_size, population_size))
    validation_start = validation_start_index(len(train_bars), validation_ratio)

    def evaluate(genes: Genes) -> tuple[BacktestResult, BacktestResult, BacktestResult | None, float]:
        if validation_start is None:
            result = backtest(
                train_bars,
                genes,
                initial_capital,
                transaction_cost,
                drawdown_penalty,
                trade_penalty,
                min_trades=min_trades,
                max_trades=max_trades,
                excess_trade_penalty=excess_trade_penalty,
                benchmark_weight=benchmark_weight,
            )
            return result, result, None, 0.0

        optimization_result = backtest(
            train_bars[:validation_start],
            genes,
            initial_capital,
            transaction_cost,
            drawdown_penalty,
            trade_penalty,
            min_trades=min_trades,
            max_trades=max_trades,
            excess_trade_penalty=excess_trade_penalty,
            benchmark_weight=benchmark_weight,
        )
        validation_result = backtest(
            train_bars,
            genes,
            initial_capital,
            transaction_cost,
            drawdown_penalty,
            trade_penalty,
            trade_start_index=validation_start,
            min_trades=min_trades,
            max_trades=max_trades,
            excess_trade_penalty=excess_trade_penalty,
            benchmark_weight=benchmark_weight,
        )
        score, overfit_gap = robust_fitness(
            optimization_result=optimization_result,
            validation_result=validation_result,
            validation_weight=validation_weight,
            overfit_penalty=overfit_penalty,
        )
        return replace(validation_result, fitness=score), optimization_result, validation_result, overfit_gap

    best_genes = population[0]
    best_result, best_optimization_result, best_validation_result, best_overfit_gap = evaluate(best_genes)

    for generation in range(1, generations + 1):
        scores: dict[Genes, BacktestResult] = {}
        optimization_scores: dict[Genes, BacktestResult] = {}
        validation_scores: dict[Genes, BacktestResult | None] = {}
        overfit_gaps: dict[Genes, float] = {}
        for genes in population:
            score_result, optimization_result, validation_result, overfit_gap = evaluate(genes)
            scores[genes] = score_result
            optimization_scores[genes] = optimization_result
            validation_scores[genes] = validation_result
            overfit_gaps[genes] = overfit_gap
        ranked = sorted(population, key=lambda genes: scores[genes].fitness, reverse=True)
        generation_best = ranked[0]
        generation_result = scores[generation_best]
        if generation_result.fitness > best_result.fitness:
            best_genes = generation_best
            best_result = generation_result
            best_optimization_result = optimization_scores[generation_best]
            best_validation_result = validation_scores[generation_best]
            best_overfit_gap = overfit_gaps[generation_best]

        if progress_callback:
            progress_callback(
                {
                    "generation": generation,
                    "population_size": population_size,
                    "evaluated_individuals": generation * population_size,
                    "validation_active": validation_start is not None,
                    "generation_best_genes": generation_best,
                    "generation_best_result": generation_result,
                    "generation_optimization_result": optimization_scores[generation_best],
                    "generation_validation_result": validation_scores[generation_best],
                    "generation_overfit_gap": overfit_gaps[generation_best],
                    "best_genes": best_genes,
                    "best_result": best_result,
                    "best_optimization_result": best_optimization_result,
                    "best_validation_result": best_validation_result,
                    "best_overfit_gap": best_overfit_gap,
                    "top_individuals": [
                        {
                            "rank": rank,
                            "genes": genes,
                            "result": scores[genes],
                            "optimization_result": optimization_scores[genes],
                            "validation_result": validation_scores[genes],
                            "overfit_gap": overfit_gaps[genes],
                        }
                        for rank, genes in enumerate(ranked[: min(5, len(ranked))], start=1)
                    ],
                }
            )

        if verbose:
            print(
                f"Geracao {generation:03d} | "
                f"fitness={generation_result.fitness:.4f} | "
                f"retorno={generation_result.total_return:.2%} | "
                f"drawdown={generation_result.max_drawdown:.2%} | "
                f"trades={generation_result.trades} | "
                f"gap_overfit={overfit_gaps[generation_best]:.2%}"
            )

        next_population = ranked[:elite_size]
        while len(next_population) < population_size:
            parent_a = tournament_selection(population, scores, rng, tournament_size=3)
            parent_b = tournament_selection(population, scores, rng, tournament_size=3)
            child = crossover(parent_a, parent_b, rng)
            child = mutate(child, rng, mutation_rate)
            next_population.append(child)
        population = next_population

    full_train_result = backtest(
        train_bars,
        best_genes,
        initial_capital,
        transaction_cost,
        drawdown_penalty,
        trade_penalty,
        min_trades=min_trades,
        max_trades=max_trades,
        excess_trade_penalty=excess_trade_penalty,
        benchmark_weight=benchmark_weight,
    )
    return best_genes, replace(full_train_result, fitness=best_result.fitness)


def split_train_test(bars: list[PriceBar], train_ratio: float) -> tuple[list[PriceBar], list[PriceBar]]:
    train_size = int(len(bars) * train_ratio)
    train_size = max(250, min(train_size, len(bars) - 90))
    return bars[:train_size], bars[train_size:]


def format_genes(genes: Genes) -> str:
    mode = "long_short" if genes.trade_mode == 1 else "long_only"
    return (
        f"trade_mode={mode}, "
        f"sma_short={genes.sma_short}, "
        f"sma_long={genes.sma_long}, "
        f"rsi_period={genes.rsi_period}, "
        f"rsi_entry={genes.rsi_entry:.2f}, "
        f"rsi_exit={genes.rsi_exit:.2f}, "
        f"ema_short={genes.ema_short}, "
        f"ema_long={genes.ema_long}, "
        f"macd=({genes.macd_fast},{genes.macd_slow},{genes.macd_signal}), "
        f"atr_period={genes.atr_period}, "
        f"atr_stop_mult={genes.atr_stop_mult:.2f}, "
        f"atr_take_mult={genes.atr_take_mult:.2f}, "
        f"min_entry_signals={genes.min_entry_signals}, "
        f"min_exit_signals={genes.min_exit_signals}, "
        f"stop_loss={genes.stop_loss:.2%}, "
        f"take_profit={genes.take_profit:.2%}, "
        f"max_hold_days={genes.max_hold_days}"
    )


def format_result(result: BacktestResult) -> str:
    profit_factor = "inf" if math.isinf(result.profit_factor) else f"{result.profit_factor:.2f}"
    return (
        f"final_equity={result.final_equity:.2f}\n"
        f"retorno_total={result.total_return:.2%}\n"
        f"retorno_anual={result.annual_return:.2%}\n"
        f"buy_and_hold={result.buy_and_hold_return:.2%}\n"
        f"vs_buy_and_hold={result.return_vs_buy_hold:.2%}\n"
        f"max_drawdown={result.max_drawdown:.2%}\n"
        f"retorno_por_drawdown={result.return_drawdown_ratio:.2f}\n"
        f"trades={result.trades} | long={result.long_trades} | short={result.short_trades}\n"
        f"trades_por_ano={result.trades_per_year:.2f}\n"
        f"win_rate={result.win_rate:.2%}\n"
        f"consistencia={result.consistency_score:.2%}\n"
        f"profit_factor={profit_factor}\n"
        f"media_por_trade={result.average_trade_return:.2%}\n"
        f"melhor_trade={result.best_trade_return:.2%}\n"
        f"pior_trade={result.worst_trade_return:.2%}\n"
        f"exposicao={result.exposure:.2%}\n"
        f"fitness={result.fitness:.4f}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Algoritmo genetico para evoluir estrategia simples em GC=F ou outro CSV do Yahoo Finance."
    )
    parser.add_argument("--csv", type=Path, help="Caminho para CSV historico do Yahoo Finance.")
    parser.add_argument("--ticker", help="Ticker do Yahoo Finance, por exemplo GC=F.")
    parser.add_argument("--start", default="2010-01-01", help="Data inicial para --ticker, formato YYYY-MM-DD.")
    parser.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat(), help="Data final para --ticker.")
    parser.add_argument("--interval", default="1d", choices=["1d", "1wk", "1mo"], help="Intervalo do Yahoo Finance.")
    parser.add_argument("--population", type=int, default=40, help="Tamanho da populacao.")
    parser.add_argument("--generations", type=int, default=30, help="Numero de geracoes.")
    parser.add_argument("--mutation-rate", type=float, default=0.18, help="Probabilidade de mutacao por gene.")
    parser.add_argument("--elite-size", type=int, default=4, help="Quantidade de melhores individuos preservados.")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="Proporcao cronologica usada para treino.")
    parser.add_argument("--initial-capital", type=float, default=10_000.0, help="Capital inicial do backtest.")
    parser.add_argument("--transaction-cost", type=float, default=0.0005, help="Custo por ordem. 0.0005 = 0.05 pct.")
    parser.add_argument("--drawdown-penalty", type=float, default=1.5, help="Penalidade aplicada ao drawdown.")
    parser.add_argument("--trade-penalty", type=float, default=0.0005, help="Penalidade por trade executado.")
    parser.add_argument("--benchmark-weight", type=float, default=0.35, help="Peso para premiar/penalizar retorno contra buy and hold.")
    parser.add_argument("--validation-ratio", type=float, default=0.2, help="Parte final do treino usada como validacao interna anti-overfitting.")
    parser.add_argument("--validation-weight", type=float, default=0.65, help="Peso da validacao interna na nota robusta.")
    parser.add_argument("--overfit-penalty", type=float, default=1.5, help="Penalidade quando treino supera validacao por margem grande.")
    parser.add_argument("--min-trades", type=int, default=2, help="Minimo de trades para uma estrategia ser considerada valida.")
    parser.add_argument("--max-trades", type=int, default=30, help="Maximo de trades antes de penalizar. 0 desativa o limite.")
    parser.add_argument("--excess-trade-penalty", type=float, default=0.002, help="Penalidade por trade acima de max-trades.")
    parser.add_argument("--seed", type=int, default=7, help="Semente aleatoria para reproducibilidade.")
    parser.add_argument("--demo-days", type=int, default=900, help="Dias sinteticos usados quando --csv nao for informado.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.csv:
        bars = load_yahoo_csv(args.csv)
        print(f"Dados carregados: {args.csv} ({len(bars)} candles)")
    elif args.ticker:
        bars = download_yahoo_history(args.ticker, args.start, args.end, args.interval)
        print(f"Dados baixados: {args.ticker} ({len(bars)} candles)")
    else:
        bars = generate_demo_gold_like_data(args.demo_days, args.seed)
        print("Nenhum CSV informado. Usando dados sinteticos apenas para demonstracao.")

    train_bars, test_bars = split_train_test(bars, args.train_ratio)
    print(f"Treino: {train_bars[0].date} ate {train_bars[-1].date} ({len(train_bars)} candles)")
    print(f"Teste:  {test_bars[0].date} ate {test_bars[-1].date} ({len(test_bars)} candles)")
    print()

    best_genes, train_result = evolve(
        train_bars=train_bars,
        population_size=args.population,
        generations=args.generations,
        mutation_rate=args.mutation_rate,
        elite_size=args.elite_size,
        seed=args.seed,
        initial_capital=args.initial_capital,
        transaction_cost=args.transaction_cost,
        drawdown_penalty=args.drawdown_penalty,
        trade_penalty=args.trade_penalty,
        validation_ratio=args.validation_ratio,
        validation_weight=args.validation_weight,
        overfit_penalty=args.overfit_penalty,
        min_trades=args.min_trades,
        max_trades=args.max_trades or None,
        excess_trade_penalty=args.excess_trade_penalty,
        benchmark_weight=args.benchmark_weight,
    )

    test_result = backtest(
        test_bars,
        best_genes,
        args.initial_capital,
        args.transaction_cost,
        args.drawdown_penalty,
        args.trade_penalty,
        min_trades=args.min_trades,
        max_trades=args.max_trades or None,
        excess_trade_penalty=args.excess_trade_penalty,
        benchmark_weight=args.benchmark_weight,
    )

    print("\nMelhores genes encontrados:")
    print(format_genes(best_genes))
    print("\nResultado no TREINO:")
    print(format_result(train_result))
    print("\nResultado no TESTE fora da amostra:")
    print(format_result(test_result))


if __name__ == "__main__":
    main()
