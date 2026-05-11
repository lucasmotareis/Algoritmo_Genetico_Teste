from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from algoritmo_genetico_ouro import (
    BacktestResult,
    Genes,
    backtest,
    download_yahoo_history,
    evolve,
    format_genes,
    format_result,
    generate_demo_gold_like_data,
    load_yahoo_csv,
    robust_walk_forward_metrics,
)


@dataclass(frozen=True)
class WalkForwardWindow:
    number: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass
class WindowResult:
    window: WalkForwardWindow
    genes: Genes
    train_result: BacktestResult
    test_result: BacktestResult
    starting_capital: float
    ending_capital: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Walk-forward backtest: otimiza no passado com AG e testa no periodo seguinte."
    )
    parser.add_argument("--csv", type=Path, help="Caminho para CSV historico do Yahoo Finance.")
    parser.add_argument("--ticker", help="Ticker do Yahoo Finance, por exemplo GC=F.")
    parser.add_argument("--start", default="2010-01-01", help="Data inicial para --ticker, formato YYYY-MM-DD.")
    parser.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat(), help="Data final para --ticker.")
    parser.add_argument("--interval", default="1d", choices=["1d", "1wk", "1mo"], help="Intervalo do Yahoo Finance.")
    parser.add_argument("--demo-days", type=int, default=1200, help="Dias sinteticos usados quando --csv/--ticker nao for informado.")
    parser.add_argument("--seed", type=int, default=7, help="Semente aleatoria.")

    parser.add_argument("--train-size", type=int, default=756, help="Candles de treino por janela. 756 ~= 3 anos diarios.")
    parser.add_argument("--test-size", type=int, default=126, help="Candles de teste por janela. 126 ~= 6 meses diarios.")
    parser.add_argument("--step-size", type=int, default=126, help="Quanto a janela avanca a cada rodada.")
    parser.add_argument(
        "--mode",
        choices=["rolling", "expanding"],
        default="rolling",
        help="rolling usa treino movel; expanding aumenta o treino desde o inicio.",
    )

    parser.add_argument("--population", type=int, default=40, help="Tamanho da populacao do AG.")
    parser.add_argument("--generations", type=int, default=100, help="Numero de geracoes do AG por janela.")
    parser.add_argument("--mutation-rate", type=float, default=0.18, help="Probabilidade de mutacao por gene.")
    parser.add_argument("--elite-size", type=int, default=4, help="Quantidade de melhores individuos preservados.")
    parser.add_argument("--initial-capital", type=float, default=10_000.0, help="Capital inicial.")
    parser.add_argument("--transaction-cost", type=float, default=0.0005, help="Custo por ordem. 0.0005 = 0.05 pct.")
    parser.add_argument("--drawdown-penalty", type=float, default=1.5, help="Penalidade de drawdown usada no fitness.")
    parser.add_argument("--trade-penalty", type=float, default=0.0005, help="Penalidade por trade usada no fitness.")
    parser.add_argument("--validation-ratio", type=float, default=0.2, help="Parte final do treino usada como validacao interna anti-overfitting.")
    parser.add_argument("--validation-weight", type=float, default=0.65, help="Peso da validacao interna na nota robusta.")
    parser.add_argument("--overfit-penalty", type=float, default=1.5, help="Penalidade quando treino supera validacao por margem grande.")
    parser.add_argument("--min-trades", type=int, default=2, help="Minimo de trades para uma estrategia ser considerada valida.")
    parser.add_argument("--max-trades", type=int, default=30, help="Maximo de trades antes de penalizar. 0 desativa o limite.")
    parser.add_argument("--excess-trade-penalty", type=float, default=0.002, help="Penalidade por trade acima de max-trades.")
    parser.add_argument("--quiet", action="store_true", help="Oculta detalhes das geracoes do AG.")
    parser.add_argument("--export-dir", type=Path, default=Path("resultados"), help="Diretorio para CSVs de saida.")
    parser.add_argument("--no-export", action="store_true", help="Nao salvar CSVs de resultado.")
    return parser.parse_args()


def load_bars(args: argparse.Namespace):
    if args.csv:
        return str(args.csv), load_yahoo_csv(args.csv)
    if args.ticker:
        return args.ticker, download_yahoo_history(args.ticker, args.start, args.end, args.interval)
    return "dados_sinteticos", generate_demo_gold_like_data(args.demo_days, args.seed)


def build_windows(total_bars: int, train_size: int, test_size: int, step_size: int, mode: str) -> list[WalkForwardWindow]:
    if train_size < 250:
        raise ValueError("train-size precisa ter pelo menos 250 candles.")
    if test_size < 20:
        raise ValueError("test-size precisa ter pelo menos 20 candles.")
    if step_size < 1:
        raise ValueError("step-size precisa ser maior que zero.")

    windows: list[WalkForwardWindow] = []
    cursor = train_size
    number = 1
    while cursor + test_size <= total_bars:
        train_start = 0 if mode == "expanding" else cursor - train_size
        train_end = cursor
        test_start = cursor
        test_end = cursor + test_size
        windows.append(
            WalkForwardWindow(
                number=number,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        cursor += step_size
        number += 1
    return windows


def calculate_max_drawdown(values: list[float]) -> float:
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)
    return max_drawdown


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_").lower()


def write_windows_csv(path: Path, bars, results: list[WindowResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "window",
                "train_start",
                "train_end",
                "test_start",
                "test_end",
                "starting_capital",
                "ending_capital",
                "test_return",
                "test_drawdown",
                "test_trades",
                "test_win_rate",
                "test_profit_factor",
                "buy_and_hold",
                "sma_short",
                "sma_long",
                "rsi_period",
                "rsi_entry",
                "rsi_exit",
                "ema_short",
                "ema_long",
                "macd_fast",
                "macd_slow",
                "macd_signal",
                "atr_period",
                "atr_stop_mult",
                "atr_take_mult",
                "min_entry_signals",
                "min_exit_signals",
                "stop_loss",
                "take_profit",
                "max_hold_days",
            ]
        )
        for item in results:
            profit_factor = "inf" if math.isinf(item.test_result.profit_factor) else f"{item.test_result.profit_factor:.8f}"
            writer.writerow(
                [
                    item.window.number,
                    bars[item.window.train_start].date,
                    bars[item.window.train_end - 1].date,
                    bars[item.window.test_start].date,
                    bars[item.window.test_end - 1].date,
                    f"{item.starting_capital:.6f}",
                    f"{item.ending_capital:.6f}",
                    f"{item.test_result.total_return:.8f}",
                    f"{item.test_result.max_drawdown:.8f}",
                    item.test_result.trades,
                    f"{item.test_result.win_rate:.8f}",
                    profit_factor,
                    f"{item.test_result.buy_and_hold_return:.8f}",
                    item.genes.sma_short,
                    item.genes.sma_long,
                    item.genes.rsi_period,
                    f"{item.genes.rsi_entry:.6f}",
                    f"{item.genes.rsi_exit:.6f}",
                    item.genes.ema_short,
                    item.genes.ema_long,
                    item.genes.macd_fast,
                    item.genes.macd_slow,
                    item.genes.macd_signal,
                    item.genes.atr_period,
                    f"{item.genes.atr_stop_mult:.6f}",
                    f"{item.genes.atr_take_mult:.6f}",
                    item.genes.min_entry_signals,
                    item.genes.min_exit_signals,
                    f"{item.genes.stop_loss:.8f}",
                    f"{item.genes.take_profit:.8f}",
                    item.genes.max_hold_days,
                ]
            )


def write_trades_csv(path: Path, results: list[WindowResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "window",
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "return_pct",
                "hold_days",
                "exit_reason",
            ]
        )
        for item in results:
            for trade in item.test_result.trade_log:
                writer.writerow(
                    [
                        item.window.number,
                        trade.entry_date,
                        trade.exit_date,
                        f"{trade.entry_price:.6f}",
                        f"{trade.exit_price:.6f}",
                        f"{trade.return_pct:.8f}",
                        trade.hold_days,
                        trade.exit_reason,
                    ]
                )


def write_equity_csv(path: Path, bars, results: list[WindowResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["window", "date", "close", "equity"])
        for item in results:
            window_bars = bars[item.window.test_start : item.window.test_end]
            for bar, equity in zip(window_bars, item.test_result.equity_curve):
                writer.writerow([item.window.number, bar.date, f"{bar.close:.6f}", f"{equity:.6f}"])


def main() -> None:
    args = parse_args()
    source, bars = load_bars(args)
    windows = build_windows(len(bars), args.train_size, args.test_size, args.step_size, args.mode)
    if not windows:
        raise ValueError("Nao ha dados suficientes para formar nenhuma janela walk-forward.")

    print(f"Fonte: {source}")
    print(f"Periodo completo: {bars[0].date} ate {bars[-1].date} ({len(bars)} candles)")
    print(f"Janelas: {len(windows)} | modo={args.mode} | treino={args.train_size} | teste={args.test_size} | passo={args.step_size}")
    print()

    current_capital = args.initial_capital
    results: list[WindowResult] = []

    for window in windows:
        train_bars = bars[window.train_start : window.train_end]
        test_bars = bars[window.test_start : window.test_end]
        print(
            f"Janela {window.number:02d}: "
            f"treino {train_bars[0].date} -> {train_bars[-1].date} | "
            f"teste {test_bars[0].date} -> {test_bars[-1].date}"
        )

        best_genes, train_result = evolve(
            train_bars=train_bars,
            population_size=args.population,
            generations=args.generations,
            mutation_rate=args.mutation_rate,
            elite_size=args.elite_size,
            seed=args.seed + window.number,
            initial_capital=args.initial_capital,
            transaction_cost=args.transaction_cost,
            drawdown_penalty=args.drawdown_penalty,
            trade_penalty=args.trade_penalty,
            verbose=not args.quiet,
            validation_ratio=args.validation_ratio,
            validation_weight=args.validation_weight,
            overfit_penalty=args.overfit_penalty,
            min_trades=args.min_trades,
            max_trades=args.max_trades or None,
            excess_trade_penalty=args.excess_trade_penalty,
        )
        context_bars = bars[window.train_start : window.test_end]
        trade_start_index = window.test_start - window.train_start
        test_result = backtest(
            bars=context_bars,
            genes=best_genes,
            initial_capital=current_capital,
            transaction_cost=args.transaction_cost,
            drawdown_penalty=args.drawdown_penalty,
            trade_penalty=args.trade_penalty,
            trade_start_index=trade_start_index,
            min_trades=args.min_trades,
            max_trades=args.max_trades or None,
            excess_trade_penalty=args.excess_trade_penalty,
        )

        results.append(
            WindowResult(
                window=window,
                genes=best_genes,
                train_result=train_result,
                test_result=test_result,
                starting_capital=current_capital,
                ending_capital=test_result.final_equity,
            )
        )
        current_capital = test_result.final_equity

        print(f"  melhores genes: {format_genes(best_genes)}")
        print(
            f"  teste: retorno={test_result.total_return:.2%} | "
            f"capital={test_result.final_equity:.2f} | "
            f"drawdown={test_result.max_drawdown:.2%} | "
            f"trades={test_result.trades} | "
            f"buy_hold={test_result.buy_and_hold_return:.2%}"
        )
        print()

    first_test = windows[0].test_start
    last_test = windows[-1].test_end - 1
    total_return = (current_capital / args.initial_capital) - 1.0
    years = max((last_test - first_test + 1) / 252, 1 / 252)
    annual_return = (current_capital / args.initial_capital) ** (1.0 / years) - 1.0
    benchmark_return = (bars[last_test].close / bars[first_test].close) - 1.0
    stitched_equity = [equity for item in results for equity in item.test_result.equity_curve]
    stitched_drawdown = calculate_max_drawdown(stitched_equity)
    total_trades = sum(item.test_result.trades for item in results)
    windows_positive = sum(1 for item in results if item.test_result.total_return > 0)
    average_train_return = sum(item.train_result.total_return for item in results) / len(results)
    robust_metrics = robust_walk_forward_metrics(
        total_return=total_return,
        buy_and_hold_return=benchmark_return,
        max_drawdown=stitched_drawdown,
        total_trades=total_trades,
        years=years,
        positive_windows=windows_positive,
        total_windows=len(results),
        average_train_return=average_train_return,
    )

    print("Resumo walk-forward fora da amostra:")
    print(f"periodo_oos={bars[first_test].date} ate {bars[last_test].date}")
    print(f"capital_final={current_capital:.2f}")
    print(f"retorno_total={total_return:.2%}")
    print(f"retorno_anual={annual_return:.2%}")
    print(f"buy_and_hold_oos={benchmark_return:.2%}")
    print(f"max_drawdown_consolidado={stitched_drawdown:.2%}")
    print(f"trades_total={total_trades}")
    print(f"janelas_positivas={windows_positive}/{len(results)}")
    print(f"vs_buy_and_hold={robust_metrics['return_vs_buy_hold']:.2%}")
    print(f"retorno_por_drawdown={robust_metrics['return_drawdown_ratio']:.2f}")
    print(f"trades_por_ano={robust_metrics['trades_per_year']:.2f}")
    print(f"score_robusto={robust_metrics['robust_score']:.4f}")
    print(f"classificacao={robust_metrics['classification']}")

    if not args.no_export:
        args.export_dir.mkdir(parents=True, exist_ok=True)
        prefix = safe_name(f"{source}_{args.mode}_wf")
        windows_path = args.export_dir / f"{prefix}_windows.csv"
        trades_path = args.export_dir / f"{prefix}_trades.csv"
        equity_path = args.export_dir / f"{prefix}_equity.csv"
        write_windows_csv(windows_path, bars, results)
        write_trades_csv(trades_path, results)
        write_equity_csv(equity_path, bars, results)
        print("\nArquivos gerados:")
        print(windows_path.resolve())
        print(trades_path.resolve())
        print(equity_path.resolve())


if __name__ == "__main__":
    main()
