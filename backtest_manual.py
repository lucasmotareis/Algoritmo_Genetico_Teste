from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime, timezone
from pathlib import Path

from algoritmo_genetico_ouro import (
    Genes,
    backtest,
    download_yahoo_history,
    format_genes,
    format_result,
    generate_demo_gold_like_data,
    load_yahoo_csv,
    normalize_genes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Roda um backtest manual de uma estrategia SMA + RSI, sem otimizar com AG."
    )
    parser.add_argument("--csv", type=Path, help="Caminho para CSV historico do Yahoo Finance.")
    parser.add_argument("--ticker", help="Ticker do Yahoo Finance, por exemplo GC=F.")
    parser.add_argument("--start", default="2010-01-01", help="Data inicial para --ticker, formato YYYY-MM-DD.")
    parser.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat(), help="Data final para --ticker.")
    parser.add_argument("--interval", default="1d", choices=["1d", "1wk", "1mo"], help="Intervalo do Yahoo Finance.")
    parser.add_argument("--demo-days", type=int, default=900, help="Dias sinteticos usados quando --csv/--ticker nao for informado.")
    parser.add_argument("--seed", type=int, default=7, help="Semente dos dados sinteticos.")

    parser.add_argument("--sma-short", type=int, default=12, help="Janela da media movel curta.")
    parser.add_argument("--sma-long", type=int, default=48, help="Janela da media movel longa.")
    parser.add_argument("--rsi-period", type=int, default=14, help="Periodo do RSI.")
    parser.add_argument("--rsi-entry", type=float, default=45.0, help="RSI maximo para entrada.")
    parser.add_argument("--rsi-exit", type=float, default=70.0, help="RSI minimo para saida.")
    parser.add_argument("--ema-short", type=int, default=12, help="Janela da EMA curta.")
    parser.add_argument("--ema-long", type=int, default=48, help="Janela da EMA longa.")
    parser.add_argument("--macd-fast", type=int, default=12, help="Janela rapida do MACD.")
    parser.add_argument("--macd-slow", type=int, default=26, help="Janela lenta do MACD.")
    parser.add_argument("--macd-signal", type=int, default=9, help="Janela de sinal do MACD.")
    parser.add_argument("--atr-period", type=int, default=14, help="Periodo do ATR.")
    parser.add_argument("--atr-stop-mult", type=float, default=2.0, help="Multiplicador de ATR para stop.")
    parser.add_argument("--atr-take-mult", type=float, default=4.0, help="Multiplicador de ATR para alvo.")
    parser.add_argument("--min-entry-signals", type=int, default=2, help="Minimo de sinais positivos para entrar.")
    parser.add_argument("--min-exit-signals", type=int, default=2, help="Minimo de sinais negativos para sair.")
    parser.add_argument("--stop-loss", type=float, default=0.03, help="Stop loss. 0.03 = 3 pct.")
    parser.add_argument("--take-profit", type=float, default=0.08, help="Take profit. 0.08 = 8 pct.")
    parser.add_argument("--max-hold-days", type=int, default=20, help="Maximo de dias posicionado.")
    parser.add_argument(
        "--trade-mode",
        choices=["long_only", "long_short"],
        default="long_only",
        help="long_only compra ou fica fora; long_short tambem permite operacoes vendidas.",
    )

    parser.add_argument("--initial-capital", type=float, default=10_000.0, help="Capital inicial.")
    parser.add_argument("--transaction-cost", type=float, default=0.0005, help="Custo por ordem. 0.0005 = 0.05 pct.")
    parser.add_argument("--drawdown-penalty", type=float, default=1.5, help="Penalidade de drawdown usada no fitness.")
    parser.add_argument("--trade-penalty", type=float, default=0.0005, help="Penalidade por trade usada no fitness.")
    parser.add_argument("--benchmark-weight", type=float, default=0.35, help="Peso para premiar/penalizar retorno contra buy and hold.")
    parser.add_argument("--export-dir", type=Path, default=Path("resultados"), help="Diretorio para CSVs de saida.")
    parser.add_argument("--no-export", action="store_true", help="Nao salvar trades/curva de capital em CSV.")
    return parser.parse_args()


def load_bars(args: argparse.Namespace):
    if args.csv:
        bars = load_yahoo_csv(args.csv)
        source = str(args.csv)
    elif args.ticker:
        bars = download_yahoo_history(args.ticker, args.start, args.end, args.interval)
        source = args.ticker
    else:
        bars = generate_demo_gold_like_data(args.demo_days, args.seed)
        source = "dados_sinteticos"
    return source, bars


def build_genes(args: argparse.Namespace) -> Genes:
    return normalize_genes(
        Genes(
            trade_mode=1 if args.trade_mode == "long_short" else 0,
            sma_short=args.sma_short,
            sma_long=args.sma_long,
            rsi_period=args.rsi_period,
            rsi_entry=args.rsi_entry,
            rsi_exit=args.rsi_exit,
            ema_short=args.ema_short,
            ema_long=args.ema_long,
            macd_fast=args.macd_fast,
            macd_slow=args.macd_slow,
            macd_signal=args.macd_signal,
            atr_period=args.atr_period,
            atr_stop_mult=args.atr_stop_mult,
            atr_take_mult=args.atr_take_mult,
            min_entry_signals=args.min_entry_signals,
            min_exit_signals=args.min_exit_signals,
            stop_loss=args.stop_loss,
            take_profit=args.take_profit,
            max_hold_days=args.max_hold_days,
        )
    )


def write_trades_csv(path: Path, result) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "entry_date",
                "side",
                "exit_date",
                "entry_price",
                "exit_price",
                "return_pct",
                "hold_days",
                "exit_reason",
            ]
        )
        for trade in result.trade_log:
            writer.writerow(
                [
                    trade.entry_date,
                    trade.side,
                    trade.exit_date,
                    f"{trade.entry_price:.6f}",
                    f"{trade.exit_price:.6f}",
                    f"{trade.return_pct:.8f}",
                    trade.hold_days,
                    trade.exit_reason,
                ]
            )


def write_equity_csv(path: Path, bars, result) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["date", "close", "equity"])
        for bar, equity in zip(bars, result.equity_curve):
            writer.writerow([bar.date, f"{bar.close:.6f}", f"{equity:.6f}"])


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_").lower()


def main() -> None:
    args = parse_args()
    source, bars = load_bars(args)
    genes = build_genes(args)
    result = backtest(
        bars=bars,
        genes=genes,
        initial_capital=args.initial_capital,
        transaction_cost=args.transaction_cost,
        drawdown_penalty=args.drawdown_penalty,
        trade_penalty=args.trade_penalty,
        benchmark_weight=args.benchmark_weight,
    )

    print(f"Fonte: {source}")
    print(f"Periodo: {bars[0].date} ate {bars[-1].date} ({len(bars)} candles)")
    print("\nEstrategia:")
    print(format_genes(genes))
    print("\nResultado do backtest:")
    print(format_result(result))

    if not args.no_export:
        args.export_dir.mkdir(parents=True, exist_ok=True)
        prefix = safe_name(source)
        trades_path = args.export_dir / f"{prefix}_trades.csv"
        equity_path = args.export_dir / f"{prefix}_equity.csv"
        write_trades_csv(trades_path, result)
        write_equity_csv(equity_path, bars, result)
        print("\nArquivos gerados:")
        print(trades_path.resolve())
        print(equity_path.resolve())

    if math.isinf(result.profit_factor):
        print("\nObservacao: profit_factor infinito significa que nao houve trade perdedor.")


if __name__ == "__main__":
    main()
