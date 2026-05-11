# Roteiro de estudo e apresentacao - Algoritmo Genetico no ouro

Este material e um guia para estudar o projeto e preparar uma fala curta, de ate
5 minutos, sobre o web app criado com apoio de IA generativa.

Tema do trabalho: usar IA generativa para criar um web app que demonstra como um
algoritmo genetico funciona aplicado a uma tarefa real.

Projeto escolhido: um sistema educacional que usa Algoritmo Genetico para testar
estrategias de compra e venda no ativo `GC=F`, futuro do ouro, usando dados
historicos do Yahoo Finance.

Aviso importante: o sistema nao e recomendacao financeira. Ele e uma ferramenta
de estudo para entender otimizacao, backtest, overfitting e avaliacao fora da
amostra.

## 1. O que voce precisa entender primeiro

Um Algoritmo Genetico, ou AG, e inspirado na evolucao natural. Em vez de tentar
descobrir uma resposta perfeita diretamente, ele cria varias respostas
candidatas, testa cada uma, escolhe as melhores, mistura suas caracteristicas e
gera uma nova populacao.

No nosso projeto, cada candidato e uma estrategia de mercado. Essa estrategia
tem parametros, que chamamos de genes. Exemplos:

- tamanho da media movel curta;
- tamanho da media movel longa;
- periodo do RSI;
- limites de entrada e saida;
- stop loss;
- take profit;
- limite maximo de dias em uma operacao.

O AG nao sabe o futuro. Ele apenas testa estrategias no passado e procura
padroes que parecam funcionar. Por isso, o cuidado principal do projeto e
reduzir o risco de decorar o passado.

## 2. Problema real escolhido

A tarefa real foi: dado um historico de precos do ouro, encontrar uma regra de
compra e venda que tenha bom comportamento fora da amostra.

Fora da amostra significa um periodo que o algoritmo nao usou diretamente para
escolher a estrategia. Isso e importante porque uma estrategia pode ficar muito
bonita no treino e falhar quando encontra dados novos.

O ativo usado foi `GC=F`, que representa futuro de ouro no Yahoo Finance. O
sistema baixa candles diarios, ou seja, dados de abertura, maxima, minima,
fechamento e volume.

## 3. Como o sistema funciona

O fluxo principal e:

1. Carregar dados historicos do ouro.
2. Criar varias estrategias aleatorias.
3. Testar cada estrategia nos dados de treino.
4. Dar uma nota chamada fitness ou score.
5. Selecionar as melhores estrategias.
6. Cruzar e mutar os genes para criar novas estrategias.
7. Repetir por varias geracoes.
8. Testar a melhor estrategia em dados fora da amostra.
9. Comparar o resultado com buy and hold.

Buy and hold e uma referencia simples: comprar o ativo no inicio e segurar ate o
fim. Se a estrategia do AG perde muito para buy and hold, ela provavelmente nao
esta sendo util.

## 4. O que a interface web demonstra

A interface mostra a execucao do AG de forma visual.

Ela permite escolher:

- fonte de dados: Yahoo Finance, dados sinteticos ou CSV;
- ticker, como `GC=F`;
- periodo inicial e final;
- populacao;
- quantidade de geracoes;
- tamanho da janela de treino e teste;
- modo treino/teste, walk-forward ou otimizacao de configuracao.

Os graficos principais mostram:

- preco real carregado;
- evolucao do score por geracao ou configuracao;
- curva de capital fora da amostra.

As tabelas mostram:

- geracoes avaliadas;
- janelas walk-forward;
- trades fora da amostra;
- configuracoes testadas no modo robusto.

## 5. Por que usamos walk-forward

O problema mais perigoso neste tipo de projeto e o overfitting.

Overfitting acontece quando o algoritmo aprende detalhes especificos do passado,
mas nao aprende uma regra que funcione bem em periodos novos.

Para reduzir isso, usamos walk-forward:

- o sistema treina em uma janela passada;
- testa na janela seguinte, que ficou fora do treino;
- anda no tempo;
- repete o processo.

Isso simula melhor uma situacao real, porque no mundo real sempre estamos
tentando decidir com base no passado e depois observando o que acontece no
futuro.

## 6. Como a nota robusta foi pensada

No inicio, a tentacao seria escolher a estrategia que deu mais lucro no passado.
Mas isso pode ser perigoso.

Entao o projeto usa uma ideia de score robusto:

```text
score = retorno_validacao - penalidade_drawdown - penalidade_trades - penalidade_overfit + bonus_consistencia
```

Em linguagem simples:

- ganhar dinheiro ajuda;
- perder muito em algum momento atrapalha;
- fazer trades demais pode indicar fragilidade;
- ir muito bem no treino e mal na validacao e sinal de overfitting;
- funcionar em varias janelas diferentes recebe bonus.

O objetivo nao e achar a estrategia mais lucrativa do passado. O objetivo e
achar uma estrategia menos fragil.

## 7. O modo Otimizar configuracao

Tambem foi criado um modo chamado `Otimizar configuracao`.

Ele testa algumas configuracoes diferentes do proprio AG, por exemplo:

- populacao maior;
- validacao mais dura;
- menos trades permitidos;
- penalidade maior contra overfitting;
- mais geracoes.

Depois, o sistema escolhe a configuracao com melhor score robusto.

Isso ainda nao e um AG controlando outro AG. E uma busca leve e controlada de
hiperparametros, suficiente para uma etapa educacional.

## 8. O que a IA generativa fez no trabalho

A IA generativa foi usada como apoio para:

- planejar a arquitetura do sistema;
- escrever o codigo Python do algoritmo genetico;
- criar o backtest;
- criar o walk-forward;
- criar a interface web;
- gerar documentacao;
- ajudar a explicar conceitos como genes, fitness, drawdown e overfitting;
- melhorar o criterio de robustez.

A decisao do problema, os ajustes e a validacao foram guiados por perguntas e
criterios humanos. A IA ajudou a acelerar a construcao e a transformar ideias em
codigo funcional.

## 9. Estrutura sugerida dos slides

Slide 1 - Titulo

Tema: Algoritmo Genetico aplicado a estrategias no ouro.

Fala principal: "Nosso trabalho mostra como um algoritmo genetico pode testar e
evoluir estrategias de compra e venda usando dados historicos reais."

Slide 2 - Problema real

Mostrar que foi escolhido o ativo `GC=F`, futuro do ouro, com dados do Yahoo
Finance.

Fala principal: "A tarefa real foi tentar encontrar uma estrategia que decida
quando comprar e vender com base no historico de precos."

Slide 3 - Como funciona o AG

Mostrar populacao, genes, fitness, selecao, cruzamento, mutacao e geracoes.

Fala principal: "Cada individuo representa uma estrategia. As melhores sao
selecionadas, misturadas e modificadas, formando novas geracoes."

Slide 4 - O web app

Mostrar a interface: preco real, score, capital fora da amostra e tabelas.

Fala principal: "A interface permite acompanhar a execucao do algoritmo e
entender se a estrategia esta evoluindo ou apenas se ajustando ao passado."

Slide 5 - Robustez e resultados

Mostrar walk-forward, comparacao com buy and hold e classificacao.

Fala principal: "O ponto mais importante foi nao buscar apenas lucro no passado,
mas testar robustez. Por isso usamos walk-forward e penalizamos overfitting."

Slide 6 - Conclusao

Mostrar aprendizados e proximos passos.

Fala principal: "O projeto demonstrou que IA generativa pode ajudar a construir
um sistema funcional, mas que a avaliacao critica continua essencial."

## 10. Roteiro de fala para ate 5 minutos

Tempo 0:00 a 0:30 - Abertura

"O nosso trabalho usa IA generativa para criar um web app que demonstra um
algoritmo genetico aplicado a uma tarefa real. A tarefa escolhida foi testar
estrategias de compra e venda no ouro, usando o ticker `GC=F` do Yahoo Finance.
O objetivo nao e recomendar investimento, mas mostrar como o algoritmo funciona
e como podemos avaliar se uma estrategia e robusta."

Tempo 0:30 a 1:20 - Explicacao do AG

"Um algoritmo genetico funciona de forma parecida com uma evolucao. Primeiro ele
cria uma populacao de solucoes aleatorias. No nosso caso, cada solucao e uma
estrategia de mercado. Os genes dessa estrategia sao parametros como medias
moveis, RSI, stop loss, take profit e tempo maximo em uma operacao. O sistema
testa cada estrategia e da uma nota. As melhores sao selecionadas, cruzadas e
sofrem pequenas mutacoes. Isso gera uma nova populacao, e o processo se repete
por varias geracoes."

Tempo 1:20 a 2:10 - Problema e dados

"Usamos dados historicos do ouro porque e um ativo real, com variacoes de preco
ao longo do tempo. O sistema baixa candles diarios, principalmente o preco de
fechamento. A estrategia tenta decidir momentos de compra e venda. Depois
comparamos o resultado com buy and hold, que seria simplesmente comprar no
inicio e segurar ate o fim. Essa comparacao e importante porque uma estrategia
complexa so faz sentido se trouxer alguma vantagem real."

Tempo 2:10 a 3:10 - Interface e demonstracao

"O web app mostra o preco real carregado, o score do algoritmo por geracao, a
curva de capital fora da amostra, os melhores genes encontrados e os trades
realizados. Tambem existe um modo walk-forward, em que o algoritmo treina em uma
janela passada e testa na janela seguinte. Isso deixa a demonstracao mais
proxima de uma situacao real, porque a estrategia e testada em dados que nao
foram usados diretamente para escolhe-la."

Tempo 3:10 a 4:10 - Robustez e overfitting

"O principal desafio e evitar overfitting. Overfitting acontece quando a
estrategia decora o passado, mas nao funciona bem em dados novos. Para combater
isso, criamos uma nota mais robusta. Ela considera retorno, drawdown, quantidade
de trades, diferenca entre treino e validacao e consistencia entre janelas. Ou
seja, o sistema nao escolhe automaticamente a estrategia mais lucrativa no
passado. Ele tenta escolher uma estrategia menos fragil."

Tempo 4:10 a 5:00 - Conclusao

"Com isso, conseguimos demonstrar um algoritmo genetico em uma aplicacao real,
com dados reais, interface web e avaliacao fora da amostra. A IA generativa foi
usada para ajudar a criar o codigo, a interface e a documentacao. O aprendizado
principal foi que criar um algoritmo e relativamente rapido com IA, mas avaliar
se ele realmente generaliza exige cuidado. Como proximos passos, poderiamos
adicionar LSTM, testar outros ativos, melhorar custos de transacao e criar uma
apresentacao automatizada com os resultados."

## 11. Perguntas que podem aparecer

Pergunta: O algoritmo preve o preco futuro?

Resposta: Nao exatamente. Nesta etapa ele nao preve o preco. Ele otimiza regras
de compra e venda com base no passado e testa se elas funcionam fora da amostra.

Pergunta: Por que nao usar apenas o maior lucro?

Resposta: Porque maior lucro no passado pode ser overfitting. Preferimos
robustez, consistencia e comparacao com buy and hold.

Pergunta: O que e drawdown?

Resposta: E a maior queda do capital a partir de um topo anterior. Ele mede o
risco de queda durante a estrategia.

Pergunta: O sistema pode operar dinheiro real?

Resposta: Nao nesta etapa. Ele e educacional e faz backtests. Operacao real
exigiria mais validacao, controle de risco, integracao com corretora e muito
cuidado.

Pergunta: Onde entra a IA generativa?

Resposta: Ela ajudou a transformar a ideia em codigo, construir a interface,
organizar as metricas e criar a documentacao. Mas o entendimento e a validacao
continuam sendo humanos.

## 12. Frase final para a apresentacao

"O projeto mostra que IA generativa pode acelerar a criacao de um sistema
complexo, mas tambem mostra que, em problemas reais, nao basta o algoritmo achar
um resultado bonito no passado. E preciso testar robustez, comparar com
referencias simples e entender os limites da solucao."
