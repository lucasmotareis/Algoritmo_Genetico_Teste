from __future__ import annotations

import argparse
import json
import math
import mimetypes
import random
import threading
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from algoritmo_genetico_ouro import (
    BacktestResult,
    Genes,
    PriceBar,
    backtest,
    calculate_max_drawdown,
    download_yahoo_history,
    evolve,
    format_genes,
    generate_demo_gold_like_data,
    load_yahoo_csv,
    robust_walk_forward_metrics,
    split_train_test,
    TRADING_DAYS,
)
from walk_forward import build_windows


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
LOG_PATH = ROOT_DIR / "web_interface.log"
RUN_LOCK = threading.Lock()


def safe_print(message: str) -> None:
    try:
        print(message, flush=True)
    except OSError:
        pass


def write_log(message: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(message.rstrip() + "\n")
    except OSError:
        pass


def finite_float(value: float) -> float | None:
    if not math.isfinite(value):
        return None
    return value


def parse_str(params: dict[str, list[str]], name: str, default: str) -> str:
    values = params.get(name)
    if not values:
        return default
    value = values[0].strip()
    return value if value else default


def parse_int(params: dict[str, list[str]], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = parse_str(params, name, str(default))
    value = int(raw)
    return max(minimum, min(maximum, value))


def parse_float(params: dict[str, list[str]], name: str, default: float, minimum: float, maximum: float) -> float:
    raw = parse_str(params, name, str(default))
    value = float(raw)
    return max(minimum, min(maximum, value))


def genes_to_dict(genes: Genes) -> dict[str, int | float | str]:
    return {
        "trade_mode": genes.trade_mode,
        "trade_mode_label": "long_short" if genes.trade_mode == 1 else "long_only",
        "sma_short": genes.sma_short,
        "sma_long": genes.sma_long,
        "rsi_period": genes.rsi_period,
        "rsi_entry": genes.rsi_entry,
        "rsi_exit": genes.rsi_exit,
        "ema_short": genes.ema_short,
        "ema_long": genes.ema_long,
        "macd_fast": genes.macd_fast,
        "macd_slow": genes.macd_slow,
        "macd_signal": genes.macd_signal,
        "atr_period": genes.atr_period,
        "atr_stop_mult": genes.atr_stop_mult,
        "atr_take_mult": genes.atr_take_mult,
        "min_entry_signals": genes.min_entry_signals,
        "min_exit_signals": genes.min_exit_signals,
        "stop_loss": genes.stop_loss,
        "take_profit": genes.take_profit,
        "max_hold_days": genes.max_hold_days,
    }


def result_to_dict(result: BacktestResult) -> dict[str, float | int | None]:
    return {
        "final_equity": finite_float(result.final_equity),
        "total_return": finite_float(result.total_return),
        "annual_return": finite_float(result.annual_return),
        "max_drawdown": finite_float(result.max_drawdown),
        "trades": result.trades,
        "long_trades": result.long_trades,
        "short_trades": result.short_trades,
        "win_rate": finite_float(result.win_rate),
        "profit_factor": finite_float(result.profit_factor),
        "average_trade_return": finite_float(result.average_trade_return),
        "best_trade_return": finite_float(result.best_trade_return),
        "worst_trade_return": finite_float(result.worst_trade_return),
        "exposure": finite_float(result.exposure),
        "buy_and_hold_return": finite_float(result.buy_and_hold_return),
        "return_vs_buy_hold": finite_float(result.return_vs_buy_hold),
        "return_drawdown_ratio": finite_float(result.return_drawdown_ratio),
        "trades_per_year": finite_float(result.trades_per_year),
        "consistency_score": finite_float(result.consistency_score),
        "fitness": finite_float(result.fitness),
    }


def market_series(bars: list[PriceBar]) -> list[dict[str, float | str]]:
    return [{"date": bar.date, "close": bar.close} for bar in bars]


def equity_series(bars: list[PriceBar], equity_curve: list[float]) -> list[dict[str, float | str]]:
    return [
        {"date": bar.date, "close": bar.close, "equity": equity}
        for bar, equity in zip(bars, equity_curve)
    ]


def trade_log(result: BacktestResult) -> list[dict[str, float | int | str]]:
    return [
        {
            "side": trade.side,
            "entry_date": trade.entry_date,
            "exit_date": trade.exit_date,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "return_pct": trade.return_pct,
            "hold_days": trade.hold_days,
            "exit_reason": trade.exit_reason,
        }
        for trade in result.trade_log
    ]


def load_bars_from_params(params: dict[str, list[str]]) -> tuple[str, list[PriceBar]]:
    source_mode = parse_str(params, "source", "ticker")
    if source_mode == "demo":
        days = parse_int(params, "demo_days", 1200, 260, 5000)
        seed = parse_int(params, "seed", 7, 1, 1_000_000)
        return "dados_sinteticos", generate_demo_gold_like_data(days, seed)

    csv_path = parse_str(params, "csv", "")
    if source_mode == "csv" and csv_path:
        path = Path(csv_path)
        if not path.is_absolute():
            path = ROOT_DIR / path
        return str(path), load_yahoo_csv(path)

    ticker = parse_str(params, "ticker", "GC=F")
    start = parse_str(params, "start", "2020-01-01")
    end = parse_str(params, "end", datetime.now(timezone.utc).date().isoformat())
    interval = parse_str(params, "interval", "1d")
    return ticker, download_yahoo_history(ticker, start, end, interval)


def build_config_candidates(
    trials: int,
    seed: int,
    population: int,
    generations: int,
    mutation_rate: float,
    elite_size: int,
    validation_ratio: float,
    validation_weight: float,
    overfit_penalty: float,
    min_trades: int,
    max_trades: int | None,
    excess_trade_penalty: float,
    benchmark_weight: float,
) -> list[dict[str, object]]:
    base_max_trades = max_trades or 30
    controlled = [
        {
            "name": "robusto_padrao",
            "population": population,
            "generations": generations,
            "mutation_rate": mutation_rate,
            "elite_size": elite_size,
            "validation_ratio": validation_ratio,
            "validation_weight": validation_weight,
            "overfit_penalty": overfit_penalty,
            "min_trades": min_trades,
            "max_trades": max_trades,
            "excess_trade_penalty": excess_trade_penalty,
            "benchmark_weight": benchmark_weight,
        },
        {
            "name": "validacao_dura",
            "population": population,
            "generations": generations,
            "mutation_rate": mutation_rate,
            "elite_size": elite_size,
            "validation_ratio": 0.30,
            "validation_weight": 0.75,
            "overfit_penalty": 2.0,
            "min_trades": max(2, min_trades),
            "max_trades": min(base_max_trades, 20),
            "excess_trade_penalty": max(excess_trade_penalty, 0.003),
            "benchmark_weight": max(benchmark_weight, 0.45),
        },
        {
            "name": "mais_flexivel",
            "population": population,
            "generations": generations,
            "mutation_rate": min(0.28, mutation_rate + 0.04),
            "elite_size": elite_size,
            "validation_ratio": 0.15,
            "validation_weight": 0.60,
            "overfit_penalty": 1.0,
            "min_trades": max(1, min_trades - 1),
            "max_trades": max(base_max_trades, 40),
            "excess_trade_penalty": excess_trade_penalty,
            "benchmark_weight": max(0.20, benchmark_weight - 0.10),
        },
        {
            "name": "poucos_trades",
            "population": population,
            "generations": generations,
            "mutation_rate": mutation_rate,
            "elite_size": elite_size,
            "validation_ratio": 0.25,
            "validation_weight": 0.70,
            "overfit_penalty": 2.5,
            "min_trades": max(2, min_trades),
            "max_trades": min(base_max_trades, 15),
            "excess_trade_penalty": max(excess_trade_penalty, 0.004),
            "benchmark_weight": max(benchmark_weight, 0.50),
        },
        {
            "name": "populacao_maior",
            "population": min(120, max(population + 10, int(population * 1.5))),
            "generations": max(20, int(generations * 0.75)),
            "mutation_rate": mutation_rate,
            "elite_size": elite_size,
            "validation_ratio": validation_ratio,
            "validation_weight": validation_weight,
            "overfit_penalty": overfit_penalty,
            "min_trades": min_trades,
            "max_trades": max_trades,
            "excess_trade_penalty": excess_trade_penalty,
            "benchmark_weight": benchmark_weight,
        },
        {
            "name": "mais_geracoes",
            "population": population,
            "generations": min(160, max(generations + 20, int(generations * 1.25))),
            "mutation_rate": max(0.10, mutation_rate - 0.03),
            "elite_size": elite_size,
            "validation_ratio": validation_ratio,
            "validation_weight": min(0.80, validation_weight + 0.05),
            "overfit_penalty": overfit_penalty,
            "min_trades": min_trades,
            "max_trades": max_trades,
            "excess_trade_penalty": excess_trade_penalty,
            "benchmark_weight": max(benchmark_weight, 0.40),
        },
    ]

    rng = random.Random(seed + 997)
    candidates = controlled[: max(1, min(trials, len(controlled)))]
    while len(candidates) < trials:
        max_trade_choice = rng.choice([15, 20, 30, 40])
        candidates.append(
            {
                "name": f"sorteada_{len(candidates) + 1}",
                "population": rng.choice([max(10, population // 2), population, min(100, population + 20)]),
                "generations": rng.choice([max(20, generations // 2), generations, min(140, generations + 30)]),
                "mutation_rate": rng.choice([0.12, 0.18, 0.24, 0.28]),
                "elite_size": elite_size,
                "validation_ratio": rng.choice([0.15, 0.20, 0.25, 0.30]),
                "validation_weight": rng.choice([0.60, 0.65, 0.70, 0.75]),
                "overfit_penalty": rng.choice([1.0, 1.5, 2.0, 2.5]),
                "min_trades": rng.choice([1, 2, 3]),
                "max_trades": max_trade_choice,
                "excess_trade_penalty": rng.choice([0.002, 0.003, 0.004]),
                "benchmark_weight": rng.choice([0.25, 0.35, 0.45, 0.55]),
            }
        )
    return candidates


def generation_payload(event: dict[str, object], extra: dict[str, object] | None = None) -> dict[str, object]:
    generation_best_result = event["generation_best_result"]
    best_result = event["best_result"]
    generation_best_genes = event["generation_best_genes"]
    best_genes = event["best_genes"]
    top_individuals = []
    for item in event["top_individuals"]:
        top_individuals.append(
            {
                "rank": item["rank"],
                "genes": genes_to_dict(item["genes"]),
                "genes_text": format_genes(item["genes"]),
                "result": result_to_dict(item["result"]),
            }
        )

    payload: dict[str, object] = {
        "type": "generation",
        "generation": event["generation"],
        "population_size": event["population_size"],
        "evaluated_individuals": event["evaluated_individuals"],
        "validation_active": event.get("validation_active", False),
        "generation_overfit_gap": finite_float(float(event.get("generation_overfit_gap", 0.0))),
        "best_overfit_gap": finite_float(float(event.get("best_overfit_gap", 0.0))),
        "generation_best": result_to_dict(generation_best_result),
        "generation_best_genes": genes_to_dict(generation_best_genes),
        "generation_best_genes_text": format_genes(generation_best_genes),
        "best": result_to_dict(best_result),
        "best_genes": genes_to_dict(best_genes),
        "best_genes_text": format_genes(best_genes),
        "top_individuals": top_individuals,
    }
    if event.get("generation_optimization_result") is not None:
        payload["generation_optimization_result"] = result_to_dict(event["generation_optimization_result"])
    if event.get("generation_validation_result") is not None:
        payload["generation_validation_result"] = result_to_dict(event["generation_validation_result"])
    if event.get("best_optimization_result") is not None:
        payload["best_optimization_result"] = result_to_dict(event["best_optimization_result"])
    if event.get("best_validation_result") is not None:
        payload["best_validation_result"] = result_to_dict(event["best_validation_result"])
    if extra:
        payload.update(extra)
    return payload


class DashboardHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        safe_print(f"{self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.serve_static(WEB_DIR / "index.html")
            return
        if parsed.path == "/health":
            self.send_json({"ok": True})
            return
        if parsed.path == "/api/run":
            self.stream_run(parse_qs(parsed.query))
            return

        requested = unquote(parsed.path.lstrip("/"))
        target = (WEB_DIR / requested).resolve()
        try:
            target.relative_to(WEB_DIR.resolve())
        except ValueError:
            self.send_error(404)
            return
        self.serve_static(target)

    def send_json(self, payload: dict[str, object]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return

        content = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def start_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

    def write_event(self, payload: dict[str, object]) -> None:
        line = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        self.wfile.write(line)
        self.wfile.flush()

    def stream_run(self, params: dict[str, list[str]]) -> None:
        self.start_stream()
        if not RUN_LOCK.acquire(blocking=False):
            self.write_event({"type": "error", "message": "Ja existe uma execucao em andamento."})
            return

        try:
            self.write_event({"type": "status", "message": "Carregando dados."})
            source, bars = load_bars_from_params(params)
            run_mode = parse_str(params, "run_mode", "simple")
            population = parse_int(params, "population", 40, 2, 500)
            generations = parse_int(params, "generations", 100, 1, 500)
            mutation_rate = parse_float(params, "mutation_rate", 0.18, 0.0, 1.0)
            elite_size = parse_int(params, "elite_size", 4, 1, population)
            train_ratio = parse_float(params, "train_ratio", 0.7, 0.55, 0.9)
            seed = parse_int(params, "seed", 7, 1, 1_000_000)
            initial_capital = parse_float(params, "initial_capital", 10_000.0, 100.0, 1_000_000_000.0)
            transaction_cost = parse_float(params, "transaction_cost", 0.0005, 0.0, 0.05)
            drawdown_penalty = parse_float(params, "drawdown_penalty", 1.5, 0.0, 10.0)
            trade_penalty = parse_float(params, "trade_penalty", 0.0005, 0.0, 0.1)
            benchmark_weight = parse_float(params, "benchmark_weight", 0.35, 0.0, 2.0)
            validation_ratio = parse_float(params, "validation_ratio", 0.2, 0.0, 0.5)
            validation_weight = parse_float(params, "validation_weight", 0.65, 0.0, 1.0)
            overfit_penalty = parse_float(params, "overfit_penalty", 1.5, 0.0, 10.0)
            min_trades = parse_int(params, "min_trades", 2, 0, 10_000)
            max_trades_value = parse_int(params, "max_trades", 30, 0, 100_000)
            max_trades = max_trades_value or None
            excess_trade_penalty = parse_float(params, "excess_trade_penalty", 0.002, 0.0, 1.0)

            if run_mode == "optimize_config":
                self.stream_config_optimization(
                    params=params,
                    source=source,
                    bars=bars,
                    population=population,
                    generations=generations,
                    mutation_rate=mutation_rate,
                    elite_size=elite_size,
                    seed=seed,
                    initial_capital=initial_capital,
                    transaction_cost=transaction_cost,
                    drawdown_penalty=drawdown_penalty,
                    trade_penalty=trade_penalty,
                    benchmark_weight=benchmark_weight,
                    validation_ratio=validation_ratio,
                    validation_weight=validation_weight,
                    overfit_penalty=overfit_penalty,
                    min_trades=min_trades,
                    max_trades=max_trades,
                    excess_trade_penalty=excess_trade_penalty,
                )
                return

            if run_mode == "walk_forward":
                self.stream_walk_forward(
                    params=params,
                    source=source,
                    bars=bars,
                    population=population,
                    generations=generations,
                    mutation_rate=mutation_rate,
                    elite_size=elite_size,
                    seed=seed,
                    initial_capital=initial_capital,
                    transaction_cost=transaction_cost,
                    drawdown_penalty=drawdown_penalty,
                    trade_penalty=trade_penalty,
                    benchmark_weight=benchmark_weight,
                    validation_ratio=validation_ratio,
                    validation_weight=validation_weight,
                    overfit_penalty=overfit_penalty,
                    min_trades=min_trades,
                    max_trades=max_trades,
                    excess_trade_penalty=excess_trade_penalty,
                )
                return

            train_bars, test_bars = split_train_test(bars, train_ratio)
            self.write_event(
                {
                    "type": "market",
                    "run_mode": "simple",
                    "source": source,
                    "bars": len(bars),
                    "first_date": bars[0].date,
                    "last_date": bars[-1].date,
                    "last_close": bars[-1].close,
                    "train_bars": len(train_bars),
                    "test_bars": len(test_bars),
                    "price_series": market_series(bars),
                }
            )
            self.write_event({"type": "status", "message": "Executando algoritmo genetico."})

            def on_progress(event: dict[str, object]) -> None:
                self.write_event(generation_payload(event, {"run_mode": "simple"}))

            best_genes, train_result = evolve(
                train_bars=train_bars,
                population_size=population,
                generations=generations,
                mutation_rate=mutation_rate,
                elite_size=elite_size,
                seed=seed,
                initial_capital=initial_capital,
                transaction_cost=transaction_cost,
                drawdown_penalty=drawdown_penalty,
                trade_penalty=trade_penalty,
                benchmark_weight=benchmark_weight,
                verbose=False,
                progress_callback=on_progress,
                validation_ratio=validation_ratio,
                validation_weight=validation_weight,
                overfit_penalty=overfit_penalty,
                min_trades=min_trades,
                max_trades=max_trades,
                excess_trade_penalty=excess_trade_penalty,
            )

            test_result = backtest(
                bars=bars,
                genes=best_genes,
                initial_capital=initial_capital,
                transaction_cost=transaction_cost,
                drawdown_penalty=drawdown_penalty,
                trade_penalty=trade_penalty,
                benchmark_weight=benchmark_weight,
                trade_start_index=len(train_bars),
                min_trades=min_trades,
                max_trades=max_trades,
                excess_trade_penalty=excess_trade_penalty,
            )
            self.write_event(
                {
                    "type": "complete",
                    "run_mode": "simple",
                    "source": source,
                    "best_genes": genes_to_dict(best_genes),
                    "best_genes_text": format_genes(best_genes),
                    "train_result": result_to_dict(train_result),
                    "test_result": result_to_dict(test_result),
                    "test_series": equity_series(test_bars, test_result.equity_curve),
                    "trades": trade_log(test_result),
                }
            )
        except BrokenPipeError:
            return
        except Exception as exc:
            self.write_event({"type": "error", "message": str(exc)})
        finally:
            RUN_LOCK.release()

    def stream_walk_forward(
        self,
        params: dict[str, list[str]],
        source: str,
        bars: list[PriceBar],
        population: int,
        generations: int,
        mutation_rate: float,
        elite_size: int,
        seed: int,
        initial_capital: float,
        transaction_cost: float,
        drawdown_penalty: float,
        trade_penalty: float,
        benchmark_weight: float,
        validation_ratio: float,
        validation_weight: float,
        overfit_penalty: float,
        min_trades: int,
        max_trades: int | None,
        excess_trade_penalty: float,
    ) -> None:
        train_size = parse_int(params, "train_size", 756, 250, max(250, len(bars) - 20))
        test_size = parse_int(params, "test_size", 126, 20, max(20, len(bars) - train_size))
        step_size = parse_int(params, "step_size", test_size, 1, max(1, test_size))
        walk_mode = parse_str(params, "walk_mode", "rolling")
        if walk_mode not in {"rolling", "expanding"}:
            walk_mode = "rolling"

        windows = build_windows(
            total_bars=len(bars),
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            mode=walk_mode,
        )
        if not windows:
            raise ValueError("Nao ha dados suficientes para formar nenhuma janela walk-forward.")

        self.write_event(
            {
                "type": "market",
                "run_mode": "walk_forward",
                "source": source,
                "bars": len(bars),
                "first_date": bars[0].date,
                "last_date": bars[-1].date,
                "last_close": bars[-1].close,
                "train_bars": train_size,
                "test_bars": test_size,
                "step_size": step_size,
                "walk_mode": walk_mode,
                "windows": len(windows),
                "price_series": market_series(bars),
            }
        )
        self.write_event({"type": "status", "message": "Executando walk-forward."})

        current_capital = initial_capital
        total_evaluated = 0
        stitched_equity: list[dict[str, float | str]] = []
        stitched_equity_values: list[float] = []
        all_trades: list[dict[str, float | int | str]] = []
        window_summaries: list[dict[str, object]] = []

        for window in windows:
            train_bars = bars[window.train_start : window.train_end]
            test_bars = bars[window.test_start : window.test_end]
            self.write_event(
                {
                    "type": "walk_window",
                    "window": window.number,
                    "total_windows": len(windows),
                    "train_start": train_bars[0].date,
                    "train_end": train_bars[-1].date,
                    "test_start": test_bars[0].date,
                    "test_end": test_bars[-1].date,
                    "starting_capital": current_capital,
                }
            )

            def on_progress(event: dict[str, object]) -> None:
                nonlocal total_evaluated
                total_evaluated += population
                self.write_event(
                    generation_payload(
                        event,
                        {
                            "run_mode": "walk_forward",
                            "window": window.number,
                            "total_windows": len(windows),
                            "window_evaluated_individuals": event["evaluated_individuals"],
                            "total_evaluated_individuals": total_evaluated,
                        },
                    )
                )

            best_genes, train_result = evolve(
                train_bars=train_bars,
                population_size=population,
                generations=generations,
                mutation_rate=mutation_rate,
                elite_size=elite_size,
                seed=seed + window.number,
                initial_capital=initial_capital,
                transaction_cost=transaction_cost,
                drawdown_penalty=drawdown_penalty,
                trade_penalty=trade_penalty,
                benchmark_weight=benchmark_weight,
                verbose=False,
                progress_callback=on_progress,
                validation_ratio=validation_ratio,
                validation_weight=validation_weight,
                overfit_penalty=overfit_penalty,
                min_trades=min_trades,
                max_trades=max_trades,
                excess_trade_penalty=excess_trade_penalty,
            )

            context_bars = bars[window.train_start : window.test_end]
            trade_start_index = window.test_start - window.train_start
            test_result = backtest(
                bars=context_bars,
                genes=best_genes,
                initial_capital=current_capital,
                transaction_cost=transaction_cost,
                drawdown_penalty=drawdown_penalty,
                trade_penalty=trade_penalty,
                benchmark_weight=benchmark_weight,
                trade_start_index=trade_start_index,
                min_trades=min_trades,
                max_trades=max_trades,
                excess_trade_penalty=excess_trade_penalty,
            )
            window_series = equity_series(test_bars, test_result.equity_curve)
            stitched_equity.extend(window_series)
            stitched_equity_values.extend(test_result.equity_curve)

            window_trades = trade_log(test_result)
            for trade in window_trades:
                trade["window"] = window.number
            all_trades.extend(window_trades)

            summary = {
                "window": window.number,
                "train_start": train_bars[0].date,
                "train_end": train_bars[-1].date,
                "test_start": test_bars[0].date,
                "test_end": test_bars[-1].date,
                "starting_capital": current_capital,
                "ending_capital": test_result.final_equity,
                "train_result": result_to_dict(train_result),
                "test_result": result_to_dict(test_result),
                "best_genes": genes_to_dict(best_genes),
                "best_genes_text": format_genes(best_genes),
                "trades": len(window_trades),
            }
            window_summaries.append(summary)
            current_capital = test_result.final_equity

            self.write_event(
                {
                    "type": "walk_window_result",
                    "window": window.number,
                    "total_windows": len(windows),
                    "summary": summary,
                    "window_series": window_series,
                }
            )

        first_test = windows[0].test_start
        last_test = windows[-1].test_end - 1
        total_return = (current_capital / initial_capital) - 1.0
        years = max((last_test - first_test + 1) / TRADING_DAYS, 1 / TRADING_DAYS)
        annual_return = (current_capital / initial_capital) ** (1.0 / years) - 1.0
        benchmark_return = (bars[last_test].close / bars[first_test].close) - 1.0
        max_drawdown = calculate_max_drawdown(stitched_equity_values)
        positive_windows = sum(1 for item in window_summaries if item["test_result"]["total_return"] > 0)
        average_train_return = sum(item["train_result"]["total_return"] for item in window_summaries) / len(window_summaries)
        robust_metrics = robust_walk_forward_metrics(
            total_return=total_return,
            buy_and_hold_return=benchmark_return,
            max_drawdown=max_drawdown,
            total_trades=len(all_trades),
            years=years,
            positive_windows=positive_windows,
            total_windows=len(windows),
            average_train_return=average_train_return,
        )

        self.write_event(
            {
                "type": "walk_complete",
                "run_mode": "walk_forward",
                "source": source,
                "period_start": bars[first_test].date,
                "period_end": bars[last_test].date,
                "summary": {
                    "final_equity": current_capital,
                    "total_return": finite_float(total_return),
                    "annual_return": finite_float(annual_return),
                    "buy_and_hold_return": finite_float(benchmark_return),
                    "max_drawdown": finite_float(max_drawdown),
                    "trades": len(all_trades),
                    "positive_windows": positive_windows,
                    "windows": len(windows),
                    **robust_metrics,
                },
                "windows": window_summaries,
                "test_series": stitched_equity,
                "trades": all_trades,
            }
        )

    def evaluate_walk_forward_config(
        self,
        bars: list[PriceBar],
        windows,
        config: dict[str, object],
        config_number: int,
        seed: int,
        initial_capital: float,
        transaction_cost: float,
        drawdown_penalty: float,
        trade_penalty: float,
        benchmark_weight: float,
    ) -> dict[str, object]:
        current_capital = initial_capital
        stitched_equity: list[dict[str, float | str]] = []
        stitched_equity_values: list[float] = []
        all_trades: list[dict[str, float | int | str]] = []
        window_summaries: list[dict[str, object]] = []

        for window in windows:
            train_bars = bars[window.train_start : window.train_end]
            test_bars = bars[window.test_start : window.test_end]
            best_genes, train_result = evolve(
                train_bars=train_bars,
                population_size=int(config["population"]),
                generations=int(config["generations"]),
                mutation_rate=float(config["mutation_rate"]),
                elite_size=int(config["elite_size"]),
                seed=seed + (config_number * 1_000) + window.number,
                initial_capital=initial_capital,
                transaction_cost=transaction_cost,
                drawdown_penalty=drawdown_penalty,
                trade_penalty=trade_penalty,
                benchmark_weight=float(config.get("benchmark_weight", benchmark_weight)),
                verbose=False,
                validation_ratio=float(config["validation_ratio"]),
                validation_weight=float(config["validation_weight"]),
                overfit_penalty=float(config["overfit_penalty"]),
                min_trades=int(config["min_trades"]),
                max_trades=config["max_trades"],
                excess_trade_penalty=float(config["excess_trade_penalty"]),
            )

            context_bars = bars[window.train_start : window.test_end]
            trade_start_index = window.test_start - window.train_start
            test_result = backtest(
                bars=context_bars,
                genes=best_genes,
                initial_capital=current_capital,
                transaction_cost=transaction_cost,
                drawdown_penalty=drawdown_penalty,
                trade_penalty=trade_penalty,
                benchmark_weight=float(config.get("benchmark_weight", benchmark_weight)),
                trade_start_index=trade_start_index,
                min_trades=int(config["min_trades"]),
                max_trades=config["max_trades"],
                excess_trade_penalty=float(config["excess_trade_penalty"]),
            )
            window_series = equity_series(test_bars, test_result.equity_curve)
            stitched_equity.extend(window_series)
            stitched_equity_values.extend(test_result.equity_curve)

            window_trades = trade_log(test_result)
            for trade in window_trades:
                trade["window"] = window.number
                trade["config"] = config_number
            all_trades.extend(window_trades)

            window_summaries.append(
                {
                    "window": window.number,
                    "train_start": train_bars[0].date,
                    "train_end": train_bars[-1].date,
                    "test_start": test_bars[0].date,
                    "test_end": test_bars[-1].date,
                    "starting_capital": current_capital,
                    "ending_capital": test_result.final_equity,
                    "train_result": result_to_dict(train_result),
                    "test_result": result_to_dict(test_result),
                    "best_genes": genes_to_dict(best_genes),
                    "best_genes_text": format_genes(best_genes),
                    "trades": len(window_trades),
                }
            )
            current_capital = test_result.final_equity

        first_test = windows[0].test_start
        last_test = windows[-1].test_end - 1
        total_return = (current_capital / initial_capital) - 1.0
        years = max((last_test - first_test + 1) / TRADING_DAYS, 1 / TRADING_DAYS)
        benchmark_return = (bars[last_test].close / bars[first_test].close) - 1.0
        max_drawdown = calculate_max_drawdown(stitched_equity_values)
        positive_windows = sum(1 for item in window_summaries if item["test_result"]["total_return"] > 0)
        average_train_return = sum(item["train_result"]["total_return"] for item in window_summaries) / len(window_summaries)
        robust_metrics = robust_walk_forward_metrics(
            total_return=total_return,
            buy_and_hold_return=benchmark_return,
            max_drawdown=max_drawdown,
            total_trades=len(all_trades),
            years=years,
            positive_windows=positive_windows,
            total_windows=len(windows),
            average_train_return=average_train_return,
        )
        summary = {
            "final_equity": current_capital,
            "total_return": finite_float(total_return),
            "annual_return": finite_float((current_capital / initial_capital) ** (1.0 / years) - 1.0),
            "buy_and_hold_return": finite_float(benchmark_return),
            "max_drawdown": finite_float(max_drawdown),
            "trades": len(all_trades),
            "positive_windows": positive_windows,
            "windows": len(windows),
            **robust_metrics,
        }
        return {
            "config_number": config_number,
            "config": config,
            "summary": summary,
            "windows": window_summaries,
            "test_series": stitched_equity,
            "trades": all_trades,
        }

    def stream_config_optimization(
        self,
        params: dict[str, list[str]],
        source: str,
        bars: list[PriceBar],
        population: int,
        generations: int,
        mutation_rate: float,
        elite_size: int,
        seed: int,
        initial_capital: float,
        transaction_cost: float,
        drawdown_penalty: float,
        trade_penalty: float,
        benchmark_weight: float,
        validation_ratio: float,
        validation_weight: float,
        overfit_penalty: float,
        min_trades: int,
        max_trades: int | None,
        excess_trade_penalty: float,
    ) -> None:
        train_size = parse_int(params, "train_size", 756, 250, max(250, len(bars) - 20))
        test_size = parse_int(params, "test_size", 126, 20, max(20, len(bars) - train_size))
        step_size = parse_int(params, "step_size", test_size, 1, max(1, test_size))
        walk_mode = parse_str(params, "walk_mode", "rolling")
        if walk_mode not in {"rolling", "expanding"}:
            walk_mode = "rolling"
        config_trials = parse_int(params, "config_trials", 8, 2, 12)
        windows = build_windows(
            total_bars=len(bars),
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
            mode=walk_mode,
        )
        if not windows:
            raise ValueError("Nao ha dados suficientes para formar nenhuma janela walk-forward.")

        candidates = build_config_candidates(
            trials=config_trials,
            seed=seed,
            population=population,
            generations=generations,
            mutation_rate=mutation_rate,
            elite_size=elite_size,
            validation_ratio=validation_ratio,
            validation_weight=validation_weight,
            overfit_penalty=overfit_penalty,
            min_trades=min_trades,
            max_trades=max_trades,
            excess_trade_penalty=excess_trade_penalty,
            benchmark_weight=benchmark_weight,
        )

        self.write_event(
            {
                "type": "market",
                "run_mode": "optimize_config",
                "source": source,
                "bars": len(bars),
                "first_date": bars[0].date,
                "last_date": bars[-1].date,
                "last_close": bars[-1].close,
                "train_bars": train_size,
                "test_bars": test_size,
                "step_size": step_size,
                "walk_mode": walk_mode,
                "windows": len(windows),
                "config_trials": len(candidates),
                "price_series": market_series(bars),
            }
        )
        self.write_event({"type": "status", "message": "Otimizando configuracoes do AG."})

        results: list[dict[str, object]] = []
        best_result: dict[str, object] | None = None
        for index, config in enumerate(candidates, start=1):
            self.write_event(
                {
                    "type": "config_start",
                    "config_number": index,
                    "total_configs": len(candidates),
                    "config": config,
                }
            )
            result = self.evaluate_walk_forward_config(
                bars=bars,
                windows=windows,
                config=config,
                config_number=index,
                seed=seed,
                initial_capital=initial_capital,
                transaction_cost=transaction_cost,
                drawdown_penalty=drawdown_penalty,
                trade_penalty=trade_penalty,
                benchmark_weight=benchmark_weight,
            )
            results.append(result)
            if best_result is None or result["summary"]["robust_score"] > best_result["summary"]["robust_score"]:
                best_result = result
            self.write_event(
                {
                    "type": "config_result",
                    "config_number": index,
                    "total_configs": len(candidates),
                    "result": {
                        "config_number": result["config_number"],
                        "config": result["config"],
                        "summary": result["summary"],
                    },
                    "best_config_number": best_result["config_number"],
                }
            )

        assert best_result is not None
        self.write_event(
            {
                "type": "config_complete",
                "run_mode": "optimize_config",
                "source": source,
                "best_config_number": best_result["config_number"],
                "best": best_result,
                "results": [
                    {
                        "config_number": item["config_number"],
                        "config": item["config"],
                        "summary": item["summary"],
                    }
                    for item in results
                ],
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interface web local para acompanhar o algoritmo genetico.")
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor local.")
    parser.add_argument("--port", type=int, default=8765, help="Porta do servidor local.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}"
    safe_print(f"Interface web disponivel em {url}")
    safe_print("Pressione Ctrl+C para parar.")
    write_log(f"Interface web disponivel em {url}")
    server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        write_log(traceback.format_exc())
        raise
