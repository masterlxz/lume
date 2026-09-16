# Pendências do Projeto

> Arquivo central de pendências — **resolvidas e não resolvidas**.
> Toda pendência encontrada em qualquer arquivo do projeto deve ser registrada aqui com um ID único.
> Ao resolver uma, marcar como `✅ Resolvida` com a sessão em que foi corrigida.
>
> Última atualização: 2026-09-16 (Sessão 16 — Fase 1.15, gestão de opções)

## Não Resolvidas

### P1 — `GET /v1/fiis/{cnpj}/properties` não distingue CNPJ desconhecido de FII sem imóvel

`data: []` é a resposta pra ambos os casos (CNPJ inexistente na CVM, e CNPJ válido de um FII de
papel/recebíveis que legitimamente não tem imóvel nenhum) — diferente de `/monthly-indicators`,
que devolve 404 pra CNPJ desconhecido. Achado na Sessão 7 ao planejar a migração do Anchor:
`fetch_property_data` (`api/app/sources/cvm_fii.py`) devolve lista vazia nos dois casos, sem
jeito de diferenciar com o dado que a própria CVM fornece — unificar o comportamento com
`/monthly-indicators` corre o risco real de classificar um FII de papel válido como "não
encontrado" na primeira chamada. Decisão consciente (confirmada com o dono do projeto): não
mexer por enquanto — consumidores (o cliente HTTP do Anchor, `data-collector/finance_api_client.py`)
devem tratar `data: []` como "sem imóvel", nunca como erro.

### P2 — `GET /v1/options/{underlying_symbol}/series` não resolve corretamente todo ticker

A raiz de opção da B3 (campo usado como `underlying_symbol`) normalmente é o ticker sem o
dígito de classe (`"PETR4"` → `"PETR"`, `"BOVA11"` → `"BOVA"`), e `options_service._root_code()`
assume exatamente isso. Achado ao vivo na Sessão 16: a Embraer negocia como `"EMBR3"` mas sua
raiz de opção registrada na B3 é `"EMBJ"` — passar `"EMBR3"` (ou `"EMBR"`) no endpoint devolve
`data: []` (nenhuma série), quando na verdade existem ~centenas de séries registradas sob
`"EMBJ"`. Não há um arquivo público conhecido que mapeie ticker→raiz de opção de forma genérica
(diferente do problema já resolvido de ticker→CNPJ de FII, Fase 1.11.3, que tem bolsai como
fonte). Decisão consciente: não perseguir uma correção genérica agora — documentar a raiz
correta caso a caso, à medida que forem descobertas ao vivo (Embraer é o único caso confirmado
até aqui).

## Resolvidas

## Resolvidas

Nenhuma ainda.
