# Guia simples do nosso sistema de Algoritmo Genetico para ouro

Data: 09/05/2026

Este material foi feito para leitura posterior, em linguagem simples. Ele nao e
recomendacao financeira. O objetivo e explicar os termos e registrar o que ja
foi construido no projeto.

## 1. Ideia geral

Estamos criando um sistema educacional para testar estrategias de compra e
venda no ativo `GC=F`, que representa o futuro do ouro no Yahoo Finance.

Por enquanto, o sistema nao usa inteligencia artificial profunda nem LSTM.
Estamos usando apenas Algoritmo Genetico, ou AG.

A ideia do AG e simples:

- criar varias estrategias aleatorias;
- testar cada estrategia em dados historicos;
- manter as melhores;
- cruzar e modificar essas estrategias;
- repetir por varias geracoes;
- depois testar a melhor estrategia em um periodo que ela ainda nao viu.

## 2. Termos importantes

Ativo: aquilo que pode ser negociado. No nosso caso, usamos o ouro via ticker
`GC=F`.

Ticker: codigo usado para identificar um ativo. Exemplo: `GC=F`.

Yahoo Finance: site/fonte de dados de mercado. Estamos usando ele para baixar o
historico de precos.

Candle: uma barra de preco em um periodo. No nosso caso, cada candle diario tem
abertura, maxima, minima e fechamento.

Fechamento: ultimo preco do candle. E o preco principal usado nos nossos testes.

Retorno: quanto o capital subiu ou caiu. Se o capital vai de 10.000 para 11.000,
o retorno foi 10%.

Buy and hold: comprar e segurar ate o fim do periodo. E uma referencia simples
para comparar se o algoritmo esta realmente fazendo algo util.

Trade: uma operacao completa, com entrada e saida.

Entrada: momento em que a estrategia compra.

Saida: momento em que a estrategia vende.

Stop loss: regra para sair quando a perda chega em um limite.

Take profit: regra para sair quando o ganho chega em um alvo.

Drawdown: queda do capital a partir do maior valor ja atingido. Exemplo: se a
carteira chegou a 12.000 e caiu para 10.800, o drawdown e 10%.

Fitness: nota que o AG da para cada estrategia. No nosso codigo, a nota favorece
retorno, mas penaliza drawdown e excesso de operacoes.

Overfitting: quando a estrategia decora o passado, mas nao funciona bem no
futuro. Esse e um dos maiores riscos do projeto.

Treino: parte dos dados usada para o AG procurar boas estrategias.

Teste: parte dos dados usada depois, para avaliar se a estrategia funciona em
dados que ela nao usou para aprender.

Fora da amostra, ou OOS: significa "out of sample". Sao dados que ficaram fora
do treino.

Backtest: teste de uma estrategia usando dados passados.

Walk-forward: forma mais realista de backtest. O sistema treina em uma janela do
passado, testa no periodo seguinte, anda no tempo e repete.

## 3. Termos do Algoritmo Genetico

Algoritmo Genetico: metodo inspirado em selecao natural. Ele cria varias
solucoes, escolhe as melhores, mistura partes delas e aplica mutacoes.

Individuo: uma estrategia completa.

Gene: um parametro da estrategia. Exemplo: periodo da media movel, limite do
RSI, stop loss ou take profit.

Populacao: conjunto de estrategias testadas em uma geracao.

Geracao: uma rodada de evolucao. Em cada geracao, o sistema testa a populacao,
escolhe os melhores individuos e cria a proxima populacao.

Cruzamento: mistura genes de duas boas estrategias para criar uma nova.

Mutacao: pequena alteracao aleatoria em algum gene.

Elite: melhores individuos que sao preservados diretamente para a proxima
geracao.

## 4. Indicadores que estamos usando

SMA: media movel simples. Ajuda a identificar tendencia.

EMA: media movel exponencial. Parecida com a SMA, mas da mais peso aos precos
recentes.

RSI: indicador de forca relativa. Ajuda a identificar quando um ativo pode estar
esticado para cima ou para baixo.

MACD: indicador de tendencia e momentum. Compara medias moveis e usa uma linha
de sinal.

ATR: indicador de volatilidade. Ajuda a medir o tamanho medio dos movimentos do
preco. Usamos isso para stops e alvos dinamicos.

## 5. Como a estrategia decide comprar e vender

Cada estrategia possui varios genes. Alguns genes definem indicadores, outros
definem regras de risco.

Sinais positivos possiveis:

- SMA curta maior que SMA longa;
- RSI abaixo do limite de entrada;
- EMA curta maior que EMA longa;
- MACD acima da linha de sinal.

O gene `min_entry_signals` define quantos sinais positivos precisam aparecer
para comprar.

Sinais negativos possiveis:

- SMA curta menor que SMA longa;
- RSI acima do limite de saida;
- EMA curta menor que EMA longa;
- MACD abaixo da linha de sinal.

O gene `min_exit_signals` define quantos sinais negativos precisam aparecer para
vender.

A saida tambem pode acontecer por:

- stop loss;
- take profit;
- stop ou alvo baseado em ATR;
- tempo maximo dentro da operacao.

## 6. O que ja foi construido

1. Script principal do Algoritmo Genetico

Arquivo: `algoritmo_genetico_ouro.py`

Esse arquivo contem:

- carregamento de dados do Yahoo Finance;
- carregamento de CSV;
- geracao de dados demonstrativos;
- indicadores tecnicos;
- backtest;
- fitness;
- criacao, cruzamento e mutacao dos genes;
- evolucao por populacao e geracoes.

2. Backtest manual

Arquivo: `backtest_manual.py`

Serve para testar uma estrategia fixa, sem usar AG. Isso ajuda a comparar uma
regra escolhida manualmente com a regra encontrada pelo algoritmo.

3. Walk-forward

Arquivo: `walk_forward.py`

Serve para testar de forma mais seria:

- treina em uma janela historica;
- testa no periodo seguinte;
- anda a janela no tempo;
- repete o processo.

Esse metodo ajuda a reduzir a ilusao de resultado causada por overfitting.

4. Interface web

Arquivos:

- `web_interface.py`;
- `web/index.html`;
- `web/styles.css`;
- `web/app.js`.

A interface mostra:

- preco historico carregado;
- ultimo fechamento;
- geracao atual;
- individuos testados;
- melhor fitness;
- melhores genes;
- curva de capital fora da amostra;
- trades feitos;
- janelas walk-forward.

## 7. Resultados observados ate agora

Uma execucao walk-forward maior em `GC=F`, de 2020 ate 2024, com populacao 40 e
25 geracoes, teve aproximadamente:

- retorno fora da amostra: 11,50%;
- retorno anual aproximado: 7,53%;
- drawdown maximo: 6,36%;
- trades: 43;
- janelas positivas: 2 de 3;
- buy and hold no mesmo periodo: 29,83%.

Interpretacao simples:

O AG melhorou em relacao a versoes anteriores, mas ainda perdeu para comprar e
segurar o ouro no mesmo periodo. Isso e importante: um algoritmo so e
interessante se ele superar alternativas simples ou se reduzir bastante o risco.

## 8. O que ainda nao estamos fazendo

Ainda nao estamos usando LSTM.

Ainda nao estamos usando MetaTrader 5.

Ainda nao estamos operando em conta real.

Ainda nao temos cotacao tick a tick em tempo real.

Ainda nao temos custos totalmente realistas, como spread, slippage, corretagem
real e tamanho minimo de contrato.

## 9. Proximos passos recomendados

1. Melhorar os custos realistas

Adicionar spread, slippage e regras de tamanho de posicao.

2. Salvar historico das execucoes

Registrar parametros, melhores genes, retorno, drawdown, trades e data da
execucao.

3. Comparar com estrategias simples

Comparar contra buy and hold, cruzamento de medias fixo, RSI fixo e estrategia
aleatoria.

4. Melhorar gestao de risco

Evitar usar sempre todo o capital em cada operacao. Adicionar risco por trade,
limite de perda e limite de drawdown.

5. Testar em mais periodos

Ver se a estrategia funciona em diferentes fases do mercado.

6. Depois estudar LSTM

A LSTM poderia virar um sinal adicional, como probabilidade de alta ou queda nos
proximos candles.

7. So depois pensar em MetaTrader 5

O caminho correto seria: backtest, walk-forward, conta demo, paper trading e so
depois uma conta real com travas de risco.

## 10. Resumo final

O sistema atual e uma plataforma de pesquisa. Ele serve para aprender,
experimentar e comparar estrategias.

A parte mais importante agora nao e "achar uma estrategia perfeita", e sim
evitar cair em resultados bonitos que so funcionam no passado.

Por isso o walk-forward e a comparacao com buy and hold sao essenciais.
