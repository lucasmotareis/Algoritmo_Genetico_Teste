# Algoritmo genetico para estrategia no ouro

Este projeto implementa uma primeira versao de algoritmo genetico para evoluir
uma estrategia simples de compra e venda usando dados historicos do Yahoo
Finance. O foco inicial e o ticker `GC=F`, futuro de ouro.

> Uso educacional. Resultado de backtest nao garante resultado futuro.

## Como rodar com dados de demonstracao

```powershell
python .\algoritmo_genetico_ouro.py --population 20 --generations 10
```

## Como rodar apenas o backtest manual

Antes de otimizar com algoritmo genetico, use este comando para testar uma
estrategia fixa:

```powershell
python .\backtest_manual.py --ticker "GC=F" --start 2020-01-01 --end 2024-12-31 --sma-short 12 --sma-long 48 --ema-short 12 --ema-long 48 --rsi-entry 55 --rsi-exit 72 --min-entry-signals 2 --min-exit-signals 2 --stop-loss 0.03 --take-profit 0.08 --max-hold-days 20
```

Ele gera dois arquivos em `resultados/`:

```text
gc_f_trades.csv
gc_f_equity.csv
```

O primeiro lista cada operacao. O segundo lista a curva de capital ao longo do
tempo.

## Como rodar walk-forward backtest

O walk-forward otimiza a estrategia em uma janela de treino e testa a melhor
configuracao no periodo seguinte. Depois, a janela anda no tempo. O modo
padrao atual prioriza robustez acima de retorno maximo.

```powershell
python .\walk_forward.py --ticker "GC=F" --start 2020-01-01 --end 2024-12-31 --train-size 756 --test-size 126 --step-size 126 --population 40 --generations 100 --quiet
```

Parametros principais:

```text
train-size  quantidade de candles usados para otimizar
test-size   quantidade de candles fora da amostra
step-size   quanto a janela anda a cada rodada
mode        rolling ou expanding
```

O modo `rolling` usa uma janela movel de treino. O modo `expanding` comeca com
uma janela minima e vai acumulando mais historico a cada rodada.

Configuracao robusta recomendada nesta etapa:

```text
population=40
generations=100
train-size=756
test-size=126
step-size=126
validation-ratio=0.20
validation-weight=0.65
overfit-penalty=1.5
min-trades=2
max-trades=30
```

## Como abrir a interface web

A interface web mostra o ultimo fechamento carregado, o progresso das geracoes,
os individuos testados, o melhor score, os genes encontrados e o resultado no
periodo de teste. Ela permite escolher entre `Treino/Teste`, `Walk-forward` e
`Otimizar configuracao`.

```powershell
python .\web_interface.py --port 8765
```

Depois acesse:

```text
http://127.0.0.1:8765
```

Ao clicar em `Iniciar`, o navegador chama o proprio script Python e recebe os
eventos da execucao em tempo real.

No modo `Walk-forward`, a tela mostra:

```text
janela atual
geracoes do AG dentro de cada janela
resultado fora da amostra por janela
curva de capital consolidada
trades fora da amostra
comparacao com buy and hold
```

No modo `Otimizar configuracao`, o sistema testa de 2 a 12 configuracoes leves
do AG usando walk-forward. A tabela mostra retorno OOS, drawdown, buy and hold,
vantagem/desvantagem contra buy and hold, janelas positivas, trades, score
robusto e parametros usados. A melhor linha e escolhida pelo score robusto, nao
apenas pelo maior retorno.

## Como rodar com o ouro do Yahoo Finance

```powershell
python .\algoritmo_genetico_ouro.py --ticker "GC=F" --start 2010-01-01 --end 2026-05-09 --population 60 --generations 40
```

## Como rodar com um CSV do Yahoo Finance

O CSV deve ter as colunas padrao do Yahoo:

```text
Date,Open,High,Low,Close,Adj Close,Volume
```

Comando:

```powershell
python .\algoritmo_genetico_ouro.py --csv .\GC-F.csv --population 60 --generations 40
```

## Genes da estrategia

Cada individuo do algoritmo genetico representa uma estrategia:

```text
sma_short      janela da media movel curta
sma_long       janela da media movel longa
rsi_period     periodo do RSI
rsi_entry      limite de RSI para entrada
rsi_exit       limite de RSI para saida
ema_short      janela da media exponencial curta
ema_long       janela da media exponencial longa
macd_fast      media rapida do MACD
macd_slow      media lenta do MACD
macd_signal    linha de sinal do MACD
atr_period     periodo do ATR
atr_stop_mult  multiplicador do ATR para stop dinamico
atr_take_mult  multiplicador do ATR para alvo dinamico
min_entry_signals  minimo de sinais positivos para comprar
min_exit_signals   minimo de sinais negativos para vender
stop_loss      perda maxima por operacao
take_profit    ganho alvo por operacao
max_hold_days  limite maximo de dias posicionado
```

## Regra de entrada e saida

Entrada:

```text
compra quando a quantidade de sinais positivos chega em min_entry_signals
```

Os sinais positivos possiveis sao:

```text
SMA curta > SMA longa
RSI <= rsi_entry
EMA curta > EMA longa
MACD > sinal do MACD
```

Saida:

```text
stop loss
take profit
stop ou alvo dinamico baseado em ATR
maximo de dias na operacao
venda quando a quantidade de sinais negativos chega em min_exit_signals
```

Os sinais negativos possiveis sao:

```text
SMA curta < SMA longa
RSI >= rsi_exit
EMA curta < EMA longa
MACD < sinal do MACD
```

No walk-forward, os indicadores do periodo de teste usam a janela de treino
como aquecimento. Assim, medias longas, MACD e ATR nao ficam sem historico logo
no inicio da janela fora da amostra.

## Fitness

A funcao de fitness favorece retorno, mas penaliza drawdown, excesso de
operacoes e sinais de overfitting:

```text
score = retorno_validacao - penalidade_drawdown - penalidade_trades - penalidade_overfit + bonus_consistencia
```

Para reduzir overfitting, o AG agora divide o proprio treino em duas partes:

```text
otimizacao  parte inicial do treino usada para procurar estrategias
validacao   parte final do treino usada para conferir se a estrategia generaliza
teste       periodo fora da amostra, usado apenas depois da escolha dos genes
```

Se uma estrategia vai muito bem na otimizacao, mas mal na validacao, ela recebe
uma penalidade. A tela mostra esse comportamento como `gap treino/validacao`.

Parametros anti-overfitting principais:

```text
validation-ratio    parte final do treino usada como validacao interna
validation-weight   peso da validacao na nota robusta
overfit-penalty     penalidade quando treino supera validacao por margem grande
min-trades          minimo de trades para a estrategia ser considerada valida
max-trades          maximo de trades antes de penalizar excesso; 0 desativa
```

O walk-forward continua sendo a validacao mais importante: ele otimiza em uma
janela passada, testa fora da amostra, anda no tempo e repete.

Metricas extras do resultado:

```text
return_vs_buy_hold       quanto a estrategia ganhou/perdeu contra buy and hold
return_drawdown_ratio    retorno dividido pelo drawdown maximo
trades_per_year          media anual de operacoes
consistency_score        proporcao de janelas positivas no walk-forward
robust_score             nota final usada para escolher a configuracao
classification           boa, instavel, provavel overfitting ou fraca contra buy and hold
```

## Proximos passos

- Salvar a melhor estrategia em JSON.
- Gerar grafico da curva de capital.
- Comparar com buy and hold e outras estrategias base.
- Adicionar filtro de volatilidade e custos variaveis por corretora.
