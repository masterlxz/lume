## Decisões de Arquitetura em Aberto

| Decisão | Opções | Status |
|---|---|---|
| Linguagem/framework da Finance API | Python (FastAPI, reaproveita o conhecimento do `data-collector` do Anchor) vs Node/TypeScript vs Rust | **Decidido (Sessão 2) — Python + FastAPI**, confirmado com o dono do projeto via `AskUserQuestion` |
| Banco de dados (Finance DB) | PostgreSQL vs SQLite (Anchor usa SQLite hoje, mas é single-consumer; Finance DB precisa servir múltiplos consumidores concorrentes) | **Decidido (Sessão 2) — PostgreSQL** (17-alpine via Docker Compose) |
| Autenticação da API | API key simples (header) vs OAuth/JWT | **Decidido (Sessão 2) — API key estática via header `X-API-Key`**, lista de chaves aceitas em `API_KEYS` (env, separadas por vírgula) — sem tabela/admin de chaves ainda, decisão consciente de MVP; virar multi-consumidor de verdade (chave por consumidor, rotação) é trabalho futuro |
| Hospedagem | Self-host (Docker, mesmo padrão do TruthID/Anchor) vs Cloud gerenciado | **Decidido (Sessão 2) — self-host via Docker Compose**, mesmo padrão usado pelo `aporte-facil` (o projeto irmão mais próximo em stack: Python + Postgres + Docker) — `docker-compose.yml` na raiz do repo, `api/` como componente (`build: ./api`); cloud gerenciado fica pra Fase 4 (Workspace) do blueprint |
| Cadência de coleta por fonte | Sob demanda (como o botão manual do Anchor) vs job agendado (cron) vs híbrido | **Pendente para as próximas fontes** — BCB SGS (Sessão 2) usa cache-through sob demanda com TTL configurável (`CACHE_TTL_SECONDS`, padrão 3600s), não cron; cadência das demais fontes do catálogo (`CONTEXT.md`) segue em aberto |
| Licença open-source | MIT (mesma do TruthID/Anchor) vs AGPL (mencionada no blueprint como opção pro open-core) | **Decidido (Sessão 2) — MIT**, mesma licença do TruthID/Anchor/aporte-facil |

---

## Catálogo técnico das fontes

Ver tabela completa (fonte × domínio × observação) em `CONTEXT.md`, seção "Catálogo de Fontes
de Dados". Esta seção registra, por fonte, decisões técnicas de implementação conforme forem
tomadas.

### BCB SGS (`api/app/sources/bcb_sgs.py`) — Sessão 2

- Biblioteca HTTP: `requests`, timeout 15s, sem retry ainda (erro vira `BcbSgsError` e propaga
  — MVP; se já existir cache pra série, o service serve stale em vez de falhar, ver
  `macro_series_service.py`).
- Séries portadas: CDI (código BCB 4391), IPCA (código BCB 433) — catálogo travado em
  `api/app/sources/catalog.py`, não adicionar código especulativo sem confirmar contra a API
  real primeiro.
- TTL de cache: configurável via `CACHE_TTL_SECONDS` (padrão 3600s).
- Upsert: `INSERT ... ON CONFLICT (series_code, reference_month) DO UPDATE` — equivalente
  Postgres do `INSERT OR REPLACE` que o Anchor usa pra essas duas séries (BCB revisa o valor do
  mês corrente depois de publicado).
- Validado ao vivo contra a API real (Sessão 2): 481 pontos de CDI (desde 1986-08),
  559 pontos de IPCA (desde ~1979), ambos servidos do cache numa segunda chamada imediata.

### Yahoo Finance (`api/app/sources/acoes_yahoo.py`) — Sessão 3

- Biblioteca HTTP: `requests`, timeout 15s, helper privado `_fetch_chart()` compartilhado
  pelas 5 funções (evita repetir o bloco try/except 5x como o Anchor faz).
- Capacidades portadas: cotação (`/quote`), técnicos SMA50/100/200 + CAGR5/10y
  (`/technicals`), dividendo médio 5 anos (`/dividends-avg`), histórico diário de preço 10
  anos (`/price-history`), histórico de pagamentos de dividendo (`/dividend-payments`) — todas
  sob `GET /v1/stocks/{ticker}/...`.
  Diferença de design vs. o Anchor: cada função recebe **um** ticker (não uma lista) — nossa
  API atende um ticker por requisição, então erro de um ticker é erro da requisição, não algo
  a "pular e continuar" (isso só faz sentido em job batch).
- TTL: `stock_quote_ttl_seconds` (padrão 300s, preço muda rápido) só pra `/quote`;
  `cache_ttl_seconds` (padrão 3600s) pras outras 4 (mudam devagar).
- Upsert: `stock_quotes`/`stock_technicals`/`stock_dividends_avg` — `ON CONFLICT DO UPDATE`
  (1 linha por ticker, sobrescrita a cada refresh). `stock_price_history`/
  `stock_dividend_payments` — `ON CONFLICT DO NOTHING` (fato histórico imutável, mesmo
  raciocínio do `INSERT OR IGNORE` que o Anchor usa pra essas duas tabelas).
- `dividends-avg` tem um terceiro estado além de sucesso/erro de fonte: "sem dado" (ticker sem
  histórico de dividendo, ex. growth stock) — não é falha, vira 404 só quando não há cache
  nenhum ainda; se já existe cache, o serviço mantém servindo o valor existente em vez de
  apagá-lo.
- Validado ao vivo contra a API real (Sessão 3, ticker PETR4): cotação R$42,70, 2.491 pontos de
  histórico de preço (desde ~2016), 34 pagamentos de dividendo, técnicos e dividendo médio
  (5y) calculados corretamente; segunda chamada de `/quote` serviu do cache
  (`cached: true`).

### CVM — DFP + FII (`api/app/sources/cvm_dfp.py` / `cvm_fii.py`) — Sessão 4

- **Estrutura bem diferente das duas fontes anteriores**: não é API por identificador — a CVM
  publica **um zip por ano** com as demonstrações financeiras de ~870 companhias juntas (DFP) e
  outro conjunto de zips pra FII (schema/convenção de nome de arquivo próprios). Endpoints
  recebem **código CVM** (empresa, int) ou **CNPJ** (fundo, normalizado pra 14 dígitos) — não
  ticker, já que a resolução ticker→identificador depende da bolsai (fonte paga, não portada
  ainda).
- **Cache de zip em disco** dentro do container (`api/.cache/cvm_dfp/`, `api/.cache/cvm_fii/`,
  gitignored) — evita rebaixar o mesmo zip quando duas capacidades da mesma empresa/fundo são
  pedidas em sequência (ex: ROE depois DCF). Efêmero (apaga num restart do container) — a fonte
  de verdade entre requisições continua o Postgres via TTL, igual às outras fontes.
- **Shape simplificado vs. o Anchor**: como `fetch_dcf_fundamentals`/`fetch_monthly_indicators`
  só devolvem o ano/mês mais recente (nunca uma série histórica), as tabelas de cache são
  **1 linha por identificador** (mesmo padrão de `stock_quotes`), não 1 linha por ano/mês como
  `macro_series_monthly`. Exceção: `fii_properties` — N linhas por fundo (vários imóveis no
  mesmo trimestre) — refresh faz **delete-e-insere** o conjunto inteiro do CNPJ numa transação,
  em vez de upsert linha a linha, pra um imóvel que saiu do relatório mais recente não ficar
  "fantasma" na base.
- TTL: `cvm_ttl_seconds` (padrão 86400s/24h) — bem maior que o das fontes de mercado, dado
  trimestral/anual. **Renomeado pra `fundamentals_ttl_seconds` na Sessão 6**, quando bolsai e
  SEC EDGAR passaram a reusar o mesmo campo (mesma semântica: fundamento trimestral/anual,
  independente da fonte).
- **Refatoração**: extraído `app/services/single_row_cache.py` (generaliza o
  `_get_or_refresh_single_row` que só existia dentro de `stock_service.py`) — com CVM esse
  padrão passa a se repetir em 4 lugares (roe, payout, dcf, monthly indicators) além dos 2 já
  existentes (quote, technicals); `stock_service.py` foi atualizado pra usar a versão
  compartilhada, mesmo comportamento, suite de testes (44 testes da Sessão 3) confirmada sem
  regressão antes de seguir.
- Validado ao vivo contra a API real (Sessão 4): VALE3 (CD_CVM 4170) — ROE 6,25%, alíquota
  efetiva 55,75% (bate exatamente com o número citado no docstring original do Anchor pra essa
  mesma empresa), payout médio 5a 61,38% (~19s, 5 zips anuais); FII CNPJ `00332266000131` —
  indicador mensal e 1 imóvel (Via Parque Shopping) retornados corretamente; 404 pra código CVM
  inexistente; cache confirmado (`cached: true` numa segunda chamada).

### Cripto — CoinGecko + DefiLlama + alternative.me + ultrasound.money — Sessão 5

- 4 fontes pequenas (1-2 chamadas HTTP cada, sem chave) alimentando 4 endpoints. Erro
  unificado num único `CryptoDataError` (`app/sources/crypto_common.py`) em vez de 1 tipo por
  fonte (padrão Yahoo/CVM) — como várias fontes alimentam os mesmos endpoints, um tipo só
  simplifica o `except` do router.
- **`/v1/crypto/eth-indicators/{indicator_code}`**: os 4 indicadores de saúde do ETH (TVL
  trend via DefiLlama, net issuance + fees vs emissão via ultrasound.money, NVT ratio via
  CoinGecko) viram **um endpoint parametrizado por código**, não 4 endpoints separados — mesmo
  padrão de `GET /v1/macro-series/{series_code}` (catálogo `indicator_code → fetch`,
  `app/sources/crypto_indicator_catalog.py`), diferente do "1 endpoint por capacidade" do
  Yahoo/CVM. Sem classificação GREEN/NEUTRAL/RED (isso é regra de negócio do Anchor, não dado
  — a Finance API serve o valor bruto, quem consome decide os thresholds).
  **Detalhe de testabilidade**: o catálogo guarda o `fetch` como uma closure que faz lookup do
  atributo do módulo em tempo de chamada (`lambda: cripto_defillama.fetch_tvl_trend_mom()`), não
  a função importada direto — importar direto congelaria a referência no momento da construção
  do dict, tornando `patch("app.sources.cripto_defillama.fetch_tvl_trend_mom")` inerte nos
  testes.
- **`/v1/crypto/{symbol}/quote`** e **`/price-history`**: cotação/histórico de qualquer moeda
  via `resolve_coin_id` (CoinGecko `/search`, match exato por símbolo, menor
  `market_cap_rank` desempata) + `fetch_market_chart`. Resolução símbolo→coin_id tem cache
  próprio (`crypto_coin_resolution`, TTL longo — `cache_ttl_seconds`) compartilhado entre
  `/quote` e `/price-history`, evita resolver de novo a cada chamada.
- TTL: `crypto_quote_ttl_seconds` (novo, 300s, mesmo valor/raciocínio do
  `stock_quote_ttl_seconds`) só pra `/quote`; `cache_ttl_seconds` (3600s) pros indicadores,
  Fear & Greed, resolução e histórico.
- Upsert: `crypto_indicators`/`crypto_fear_greed`/`crypto_coin_resolution`/`crypto_quotes` —
  `ON CONFLICT DO UPDATE` (1 linha, sobrescrita). `crypto_fear_greed` é singleton (`id` sempre
  `1`). `crypto_price_history` — `ON CONFLICT DO NOTHING` (append-only).
- **Refatoração**: extraído `app/services/append_only_list_cache.py` (generaliza o
  `_get_or_refresh_list` que só existia em `stock_service.py`) — 2º uso real do shape
  (`crypto_price_history`); `stock_service.py` atualizado pra usar a versão compartilhada,
  suite completa (83 testes) confirmada sem regressão antes de seguir.
- Validado ao vivo (Sessão 5): os 4 indicadores do ETH com valores reais (TVL trend +21,4%,
  net issuance +0,86% anualizado, fees/emissão 0,015, NVT ratio 0,79), Fear & Greed (73,
  "Greed"), BTC quote (~US$80.462) e 365 pontos de histórico; cache confirmado; 404 pra
  indicador/símbolo desconhecido.

### B3 index stats + Yahoo Metais + bolsai + SEC EDGAR — Sessão 6 (fecha a Fase 1.6)

- **Achado ao reler `stocks.py`**: `acoes_yahoo.fetch_quote`/`fetch_price_history` usam
  `suffix=".SA"` por padrão e `stock_service.py` nunca sobrescrevia isso — ou seja,
  `/v1/stocks/{ticker}/...` só serve tickers B3. SEC EDGAR é mercado americano — por isso ganha
  namespace próprio (`/v1/us-stocks/{ticker}/...`) em vez de reaproveitar `/v1/stocks/`.
- **B3 index stats** (`api/app/sources/b3_index_stats.py`): catálogo travado a 3 índices já
  validados pelo Anchor — IFIX (base 2010), SMLL/IDIV (base 2005), ano-base fixo por índice
  (`app/sources/b3_index_catalog.py`), não exposto como parâmetro. `GET
  /v1/b3-indexes/{index_code}/history`, upsert `ON CONFLICT DO NOTHING` (histórico imutável).
  Validado ao vivo: IFIX, 3.885 pontos desde 2010-12-30.
- **Yahoo Metais** (`api/app/sources/metals_catalog.py`): **sem cliente HTTP próprio** — reusa
  `acoes_yahoo.fetch_quote`/`fetch_price_history` diretamente com `suffix=""` (metal não é
  listado na B3), só um catálogo de 4 símbolos (XAU/XAG/XPT/XPD → GC=F/SI=F/PL=F/PA=F). `GET
  /v1/metals/{metal_code}/quote` e `/price-history`. Preço sempre em onça troy, sem conversão
  (decisão do dono do projeto, herdada do Anchor). Validado ao vivo: ouro (XAU) cotado
  corretamente.
- **bolsai** (`api/app/sources/acoes_bolsai.py`): chave copiada de `anchor/data-collector/.env`
  (mesma que o Anchor já usa em produção). `GET /v1/stocks/{ticker}/bolsai-fundamentals` — entra
  no router `stocks.py` já existente (mesmo espaço de tickers BR). Expõe `cvm_code` no retorno,
  deixando o consumidor encadear pra `/v1/companies/{cvm_code}/...` sem precisar de bolsai por
  conta própria. **Ressalva conhecida (herdada do Anchor)**: o campo `roe` da bolsai mistura
  lucro trimestral com TTM dependendo da empresa — exposto como veio da fonte mesmo assim (a
  Finance API é uma camada de dados, não corrige silenciosamente o que a fonte devolve); pra ROE
  confiável, usar `/v1/companies/{cvm_code}/roe` (calculado direto da CVM). Validado ao vivo:
  PETR4 → `cvm_code: "9512"`, ROE 28,26%.
- **SEC EDGAR** (`api/app/sources/sec_edgar.py`): cache de resolução ticker→CIK
  (`sec_edgar_cik_resolution`), mesmo padrão do `crypto_coin_resolution` — reaproveitado entre
  `/fundamentals`, `/dcf-fundamentals` e `/payout`. Rate limit ~9 req/s (`_get()` com
  `time.sleep`, um único timestamp global) portado como está do Anchor — **não é thread-safe
  sob concorrência** (FastAPI roda rotas síncronas num threadpool); aceitável no tráfego de um
  MVP, não resolvido com lock agora — registrar aqui se algum dia virar gargalo real. Validado
  ao vivo (AAPL): LPA 7,46 / VPA 4,99 / ROE 151,9%, EBIT US$133.050mi, alíquota 15,61%, payout
  médio 5a 15,08% (número real conhecido — a Apple retém a maior parte do lucro pra buyback em
  vez de dividendo). **JPM (banco) retornou 404 em `/dcf-fundamentals` como esperado** — mesma
  lacuna de taxonomia (EBIT/estoque/contas a receber-pagar não reportados do jeito
  não-financeiro) já documentada pelo Anchor, confirmando que a lógica de descarte foi portada
  corretamente.

### Rates — Meta Selic diária + curva DI futuro — Sessão 14 (fecha a Fase 1.13)

- **Selic** (`api/app/sources/bcb_sgs.py`, `fetch_daily_series`): mesma fonte de CDI/IPCA, código
  432 (Meta Selic definida pelo Copom). Catálogo próprio (`selic_catalog.py`), deliberadamente
  separado de `catalog.py` — aquele é explicitamente mensal, este é diário, shapes diferentes.
  **Limite real do BCB SGS descoberto ao vivo**: uma busca sem `dataInicial` numa série diária
  devolve HTTP 406 ("janela de consulta de, no máximo, 10 anos") — só afeta séries diárias,
  por isso `fetch_monthly_series` nunca bateu nisso. `fetch_daily_series` pagina em janelas de 9
  anos desde 1994 (janelas antes do início real da série voltam vazias, sem erro — mesmo
  raciocínio do `b3_index_stats.py` pra anos antes da base de um índice).
- **DI futuro / curva PRE** (`api/app/sources/b3_taxa_swap.py`): sistema legado "Pesquisa por
  Pregão" da B3 (`www.b3.com.br/pesquisapregao/download?filelist=TS{YYMMDD}.ex_,`) — diferente do
  UP2DATA novo, que passou a exigir sessão/Cloudflare a partir de dez/2025 (pesquisado e
  descartado antes de achar essa alternativa). Arquivo é um zip externo contendo um blob
  self-extracting que embute um zip interno com `TaxaSwap.txt` (texto de largura fixa, latin-1);
  cliente filtra só a curva `PRE` (DIxPRE). TLS validou normalmente nos testes ao vivo — ao
  contrário de uma implementação de referência (`pyettj`, lib externa consultada como ponto de
  partida) que desabilita verificação de certificado, aqui não. Data sem pregão (fim de
  semana/feriado) devolve HTTP 200 com zip de 22 bytes — tratado como lista vazia, não erro.
- **Reuso do helper genérico sem modificação**: os dois models novos (`selic_daily`,
  `di_futures_curve`) usam `get_or_refresh_list` (`append_only_list_cache.py`) tal como está — a
  curva DI parecia precisar de uma chave composta de 3 colunas (entidade + data + vértice), mas
  não tem entidade nenhuma além da própria data de referência: `reference_date` faz o papel de
  id_column e `dias_uteis` o de date_column, o mesmo truque que `reference_year` já fazia pro
  REIT (Fase 1.11.2). Novo domínio `rates.py` (router + service), não estende `macro_series.py`
  — mantém o contrato já publicado (CDI/IPCA) intocado.
- Validado ao vivo (Sessão 14): Meta Selic com 10.058 pontos desde 1999-03-05 (14,00% a.a.
  atual); curva DI de 2026-09-15 com 272 vértices (vértice de 1 dia 13,90% a.a., batendo
  exatamente com a série BCB 1178 do mesmo dia — validação cruzada entre as duas fontes novas);
  domingo (2026-09-13) e slug Selic desconhecido retornando 404; cache confirmado nas 2ª
  chamadas. Suite completa 225/225 sem regressão.

### Currencies — Câmbio multi-moeda — Sessão 15 (fecha o item de brainstorm)

- **Decisão de catálogo, o ponto central desta feature**: diferente de todo catálogo anterior
  do projeto (metais, indicadores cripto, índices B3, slugs Selic — todos mapeamentos opacos
  código→identificador-de-fonte), a conversão par-de-moeda→ticker Yahoo é **mecânica**
  (`"eurusd"` → `"EURUSD=X"`, só maiúsculas). Catalogar *pares* fixos, como `metals_catalog.py`
  faz pra seus 4 metais, contrariaria o próprio pedido ("moedas quaisquer"). `currency_catalog.py`
  whitelista **moedas individuais** (17 códigos ISO 4217), e um par é válido sse as duas metades
  estão no catálogo e diferem — `resolve_pair()` roda **antes** de qualquer chamada ao Yahoo,
  mantendo a convenção de "sem código especulativo" que todo outro catálogo do projeto já segue,
  mesmo esse catálogo sendo estruturalmente diferente (moedas, não pares).
- **Nenhum cliente HTTP novo**: reaproveita `app/sources/acoes_yahoo.py` diretamente
  (`fetch_quote`/`fetch_price_history` com `suffix=""`), mesmo padrão de reuso que
  `metals_catalog.py` já estabeleceu. `CurrencyQuote`/`CurrencyPriceHistory`
  (`api/app/models/currency.py`) reaproveitam `single_row_cache.get_or_refresh_single_row` e
  `append_only_list_cache.get_or_refresh_list` sem nenhuma modificação — só `pair_code` no lugar
  de `metal_code`.
- **Sem coluna `name` persistida** (diferente de `MetalQuote`): `base_currency`/`quote_currency`
  são deriváveis de `pair_code` por simples split de string, então o service computa os dois em
  tempo de leitura em vez de persistir um valor redundante.
- **TTL**: reaproveita `stock_quote_ttl_seconds` (quote) e `cache_ttl_seconds` (price-history)
  existentes — mesma decisão que metais já tomou, nenhum campo novo em `Settings`.
- **Limitação conhecida, deliberadamente evitada por curadoria** (não é débito técnico): moedas
  de valor ultra-baixo como VND fazem o Yahoo arredondar a cotação pra `0,0` na própria precisão
  reportada pela API — descoberto ao vivo durante a pesquisa. A lista curada de 17 moedas
  (majors G10-ish, BRL, CNY, Mercosul/LatAm) evita esse caso por construção, em vez de tentar
  corrigi-lo com mais casas decimais ou uma fonte alternativa.
- Validado ao vivo (Sessão 15): `eurusd` (1,1539 USD), `usdbrl` (5,1402 BRL), `gbpjpy` (cross
  entre duas moedas não-BRL, 208,529 JPY — a prova de que "moedas quaisquer" funciona de ponta a
  ponta pela nossa própria camada de catálogo+cache, não só no Yahoo), `arsusd`/`copbrl` (pares
  LatAm), `usdusd` e par com componente desconhecido (`xyzusd`) retornando 404 sem nenhuma
  chamada ao Yahoo, cache confirmado na 2ª chamada, histórico de `eurusd` com 2.601 pontos desde
  2016-09-15. Suite completa 234/234 sem regressão (+9 testes novos).

### Options — catálogo de séries + cotação EOD — Sessão 16 (fecha a Fase 1.15)

- **Primeiro domínio com cache global, não por identificador**: toda fonte anterior busca dado
  parametrizado por um id (ticker, CNPJ, par de moeda) — `single_row_cache.py`/
  `append_only_list_cache.py` são construídos em cima dessa premissa. As duas fontes novas
  (`b3_options_series.py`, `b3_cotahist.py`) devolvem o mercado inteiro numa chamada só, então
  `options_service.py` não reaproveita os dois helpers genéricos: rastreia frescor via
  `MAX(fetched_at)` da tabela toda (não por `underlying_symbol`) e, se velho, refaz a tabela
  inteira (delete-e-reinsere pra `option_series`, mesmo raciocínio de `FiiProperty` — uma série
  desregistrada deve sumir; upsert em massa por `series_ticker` pra `option_eod_quotes`) antes de
  responder com um `SELECT ... WHERE underlying_symbol = ...` comum. Documentado aqui porque é
  uma forma de "cadência de coleta" nova em relação à linha ainda aberta na tabela de decisões
  de arquitetura no topo deste arquivo.
- **Sem cache em disco do zip** (diferente de `cvm_dfp.py`): como o refresh já é gated pelo TTL
  global (`options_ttl_seconds`, 86400s) e não por request individual, baixar de novo só quando
  o TTL expira já evita o custo repetido — o cache em disco da CVM existe porque lá o fetch
  acontece por-empresa mesmo sem nada estar "velho" globalmente; aqui não.
- **`option_eod_quotes` é 1 linha por série, não append-only**: o desenho original do `/plan`
  previa a tabela como histórico (chave composta `series_ticker, trade_date`), mas como o
  COTAHIST tem que ser escaneado por inteiro de qualquer forma e o endpoint só usa o preço
  *mais recente*, guardar histórico seria puro desperdício — virou uma tabela de 1 linha por
  série (mesmo formato de `StockQuote`), decisão tomada durante a implementação ao perceber o
  parser já calcula o máximo por série em memória.
- **`b3_cotahist.py`**: confirmado ao vivo que não existe arquivo diário público
  (`COTAHIST_D{ddmmyy}.ZIP` devolve uma página de erro) — só o anual
  (`COTAHIST_A{yyyy}.ZIP`, ~80MB comprimido/700MB descomprimido pra 2026, ~2,8M linhas de
  largura fixa 245 bytes). 86% das linhas são de opção (`TPMERC` 070=compra/080=venda);
  confirmado que toda linha de opção já representa um negócio real (`TOTNEG` nunca `0`), sem
  necessidade de filtro extra. Offsets de coluna verificados contra linhas reais, cruzando
  `PREULT`/`PREEXE`/`DATVEN` da mesma série no mesmo dia com o snapshot do
  `b3_options_series.py` — inclusive um ajuste real de strike por evento corporativo (PETRJ199
  passou de 18,80 pra 17,61 entre pregões), confirmando que `PREEXE` reflete o strike vigente,
  não um valor congelado.
- **`b3_options_series.py`**: arquivo pipe-delimited (não largura fixa), dois formatos de linha
  no mesmo arquivo — tipo "02" (ação/ETF, ~85 mil das ~87 mil linhas) e tipo "03" (opção de
  índice em pontos, ex. IBOVESPA/SMALL CAP, liquidação em R$/ponto, formato de coluna
  totalmente diferente). Tipo "03" ficou **fora de escopo** — exposição a índice já é coberta
  por BOVA11 (tipo "02" comum), e o contrato de índice em pontos é um instrumento
  estruturalmente diferente. Confirmado ao vivo que a raiz de opção (campo do ativo-objeto)
  sempre é prefixo exato do ticker de série (zero exceções em ~85 mil linhas), mas **não** é
  sempre igual ao ticker de ação menos o dígito de classe — Embraer negocia "EMBR3" mas sua
  raiz de opção é "EMBJ" — gap conhecido, aceito e documentado em código (`_root_code()` em
  `options_service.py`), mesmo espírito dos achados de CNPJ truncado/fundo renomeado já
  registrados em `PENDING.md`.
- **Endpoint único, sem validação de catálogo**: `GET /v1/options/{underlying_symbol}/series`
  aceita qualquer string (diferente de `currencies`/`metals`, que validam contra um catálogo
  antes de tocar a rede) — como a fonte já é uma tabela local pós-refresh, um ativo-objeto sem
  série registrada é só uma query vazia, sem custo de rede a evitar. `data: []` pra
  ativo-objeto desconhecido, `200` sempre (nunca 404), mesmo raciocínio de
  `/v1/fiis/{cnpj}/properties`.
- Validado ao vivo (Sessão 16): primeira chamada real (`PETR4`) ~2min (download+parse do
  COTAHIST anual — mesma ordem de grandeza dos ~19s que a CVM já leva pra 5 zips anuais),
  4.356 séries, cruzado byte-a-byte contra o COTAHIST decodificado à mão (PETRJ199: strike
  17,61, último preço 31,85 em 2026-09-14); segunda chamada 0,46s com `cached: true`; `BOVA11`
  e `VALE3` com séries reais; `XYZW9` (inexistente) com `data: []`; nenhum cache em disco
  criado. Suite completa **249/249** sem regressão (+15 testes novos).

### Option greeks — Black-Scholes — Sessão 16 (fecha a Fase 1.16)

- **Primeiro recurso do projeto sem tabela/migration própria**: gregas são uma view computada
  sobre 4 fontes já cacheadas de forma independente (série+cotação EOD da opção, Fase 1.15;
  cotação do ativo-objeto, `stock_service.py`; curva DI futuro, Fase 1.13) — persistir o
  resultado não faria sentido (muda a cada tick do preço do ativo-objeto, um "cache" de grega
  estaria sempre desatualizado). `option_greeks_service.py` só orquestra a leitura das quatro e
  computa; nenhum TTL próprio.
- **Preço do ativo-objeto vem do chamador, não é adivinhado**: `option_series.underlying_symbol`
  (Fase 1.15) é só a raiz da opção (ex: "PETR"), sem dígito de classe — decisão confirmada com o
  dono do projeto de expor `underlying_ticker` como parâmetro obrigatório do endpoint de gregas
  em vez de tentar derivar a classe certa (ON/PN/PNA/...) automaticamente. Motivo: a Fase 1.15
  já achou um caso real onde a raiz não é derivável do ticker (Embraer, `PENDING.md` P2) —
  arriscar a mesma heurística pra escolher qual classe cotar poderia calcular uma grega com o
  preço do papel errado, silenciosamente. Quem já gerencia a posição sabe o ticker certo; a API
  só busca a cotação (reaproveitando `stock_service.get_or_refresh_quote`, mesmo cache de
  sempre) em vez de confiar num número cru vindo de fora.
- **`black_scholes.py`**: matemática pura, stdlib `math` (`erf` pra CDF normal) — projeto não
  tinha nenhuma dependência de cálculo numérico (`requirements.txt`), uma fórmula fechada não
  justifica introduzir numpy/scipy. Fórmulas validadas contra o caso de referência de
  livro-texto (Hull) antes de confiar na implementação. IV resolvida via Newton-Raphson
  (vega como derivada) com fallback pra bisseção — `None` explícito (não uma exceção lá dentro)
  quando o preço de mercado está abaixo do valor intrínseco, sinal de preço desatualizado, não
  bug do solver. Estilo americano (`option_series.style`) não é distinguido — só aproximação
  europeia, simplificação consciente documentada em código (sem fonte grátis pra validar prêmio
  de exercício antecipado).
- **Curva DI interpolada por dias corridos, não dias úteis**: evita ter que implementar um
  calendário de feriados brasileiro só pra isso — `T` da opção usa a mesma base (dias
  corridos/365), então os dois lados da interpolação são consistentes entre si mesmo sendo uma
  aproximação (dias corridos, não úteis) do que um book de precificação profissional usaria.
  Fora do intervalo publicado pela curva, usa o vértice mais próximo (sem extrapolar). Mesmo
  padrão de recuo dia-a-dia (até 10 dias) em cima de `NoCurveDataError` que a curva em si já usa
  pra fim de semana/feriado (Fase 1.13).
- **IV calculada a partir do último preço *realmente* negociado, que pode ser antigo**: séries
  pouco líquidas (Fase 1.15) têm `last_trade_date` de dias ou semanas atrás — a resposta expõe
  esse campo explicitamente em vez de esconder a proveniência do preço usado, mesmo raciocínio
  de não fazer julgamento de negócio que não é da API (ex: Fear&Greed cru sem classificação,
  Fase 1.5) — quem consome decide se a marcação está boa o bastante.
- **Refactor pequeno em `options_service.py`**: os dois refreshes globais internos da Fase 1.15
  (`_refresh_series_catalog_if_stale`/`_refresh_eod_quotes_if_stale`) viraram públicos
  (`refresh_series_catalog_if_stale`/`refresh_eod_quotes_if_stale`) pra `option_greeks_service.py`
  reaproveitar sem duplicar a lógica de cache global — mesmo mecanismo, só chamado de dois
  lugares agora.
- Validado ao vivo (Sessão 16): fórmulas conferidas contra o caso de referência antes de
  implementar; `PETRL522` (call PETR4 dez/2026, strike 49,91, spot 49,06) devolveu delta 0,576,
  gamma 0,034, theta -0,033/dia, vega 0,097, IV 46,49% — faixa plausível pra uma ação de
  commodity brasileira; taxa livre de risco 13,59% interpolada da curva DI de 2026-09-15 (o dia
  anterior — a curva de hoje ainda não estava publicada no momento do teste, fallback
  funcionou); série desconhecida e série nunca negociada (`PETRU696`) retornando 404; segunda
  chamada em 0,25s (tudo em cache, nenhuma rede nova). Suite completa **266/266** sem regressão
  (+17 testes novos, incluindo round-trip de IV: gera preço BS com vol conhecida, confirma que o
  solver reconstrói a mesma vol).

---

## Débitos Técnicos de Arquitetura

Nenhum ainda.
