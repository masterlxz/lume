## Log de Sessões

### 2026-08-27 — Sessão 1

**Objetivo**: bootstrap do projeto EasyBusiness a partir do blueprint original
(`blueprint_plataforma_opensource.md.docx`).

**O que foi feito**:
- Lido o blueprint (`.docx`, extraído via `python3`/`zipfile` já que não havia `pandoc`/
  `python-docx` disponíveis no ambiente) — descreve uma plataforma de 3 camadas (APIs/SDKs,
  Workspace web, módulo B3).
- Decidido, junto com o dono do projeto, que o MVP começa pela camada financeira: uma "Finance
  API" alimentando um "Finance DB" central, com o objetivo declarado de centralizar
  a coleta de dados que hoje está espalhada no projeto Anchor.
- Estudado `anchor/data-collector/sources/` (12 clientes Python: Yahoo Finance, bolsai, B3,
  BCB SGS, CVM DFP/FII, SEC EDGAR, Yahoo Metais, CoinGecko, DefiLlama, alternative.me,
  ultrasound.money) — catalogado em `CONTEXT.md` como ponto de partida da Fase 1.
- Estudada a estrutura `project/` do TruthID
  (`INDEX/OVERVIEW/CONTEXT/ARCHITECTURE/GUIDELINES/PHASE/ROADMAP/PENDING/SESSIONS.md`) como
  modelo — replicada aqui com conteúdo próprio do EasyBusiness (sem `AUTH_FLOW.md`, que é
  específico do fluxo de login do TruthID).
- Criado o repositório público `masterlxz/easybusiness` no GitHub.
- Removido `blueprint_plataforma_opensource.md.docx` do repo — conteúdo já incorporado em
  `CONTEXT.md`/`ROADMAP.md`.

**Estado ao final**: `project/` criado com as 9 páginas; nenhum código escrito ainda (Fase 1,
etapa 1.2, decidir a stack, é o próximo passo).

### 2026-08-27 — Sessão 2

**Objetivo**: primeira prova de conceito ponta a ponta da Finance API (Fase 1, etapas 1.2-1.5).

**O que foi feito**:
- Stack decidida com o dono do projeto via `AskUserQuestion`: Python + FastAPI (reaproveita o
  conhecimento do `data-collector` do Anchor).
- Pesquisado `aporte-facil` (outro projeto do autor) como referência de infraestrutura — é o
  único projeto irmão já rodando Python + PostgreSQL via Docker Compose; seguido o mesmo padrão
  (`docker-compose.yml` na raiz orquestrando componentes por pasta, `user: "1000:1000"` pra
  evitar arquivos root via bind mount, credenciais fixas em dev).
- Criado o componente `api/` (FastAPI + SQLAlchemy + Alembic): `app/config.py` (settings via
  env), `app/database.py`, `app/auth.py` (API key estática via header `X-API-Key`),
  `app/models/macro_series.py` (tabela `macro_series_monthly`, PK composta
  series_code+reference_month), `app/sources/bcb_sgs.py` (cliente BCB SGS reimplementado a
  partir de `anchor/data-collector/sources/bcb_sgs.py`), `app/sources/catalog.py` (catálogo
  travado: só CDI e IPCA, as séries já validadas em produção pelo Anchor),
  `app/services/macro_series_service.py` (cache-through: serve do Postgres se fresco, senão
  busca na fonte e faz upsert via `ON CONFLICT DO UPDATE`), `app/routers/macro_series.py`
  (`GET /v1/macro-series/{series_code}`).
- Migration Alembic inicial (`0001_create_macro_series_monthly`).
- `docker-compose.yml` (raiz), `api/Dockerfile`, `.env.example`, `requirements.txt`.
- `README.md`, `LICENSE` (MIT, mesmo texto do `anchor/LICENSE`) e `.gitignore` criados na raiz
  do repo — antes só existia `project/`.
- 14 testes automatizados (mockados, sem rede real) cobrindo o cliente BCB SGS, o service de
  cache-through e o router — dois bugs reais achados e corrigidos pelos próprios testes: (1) o
  parsing da resposta do BCB não estava dentro do `try/except`, então um payload malformado
  vazava `KeyError` cru em vez de virar `BcbSgsError`; (2) `alembic.ini` sem
  `prepend_sys_path = .` fazia o `ModuleNotFoundError: No module named 'app'` no `alembic
  upgrade head` dentro do container (cwd `/app` não entra em `sys.path` sozinho pra um console
  script instalado).
- Validado ao vivo contra a API real do BCB (`docker compose up`, sem mock): CDI (481 pontos
  desde 1986-08) e IPCA (559 pontos) retornados com sucesso; segunda chamada imediata serviu do
  Postgres (`cached: true`, sem bater no BCB de novo); 401 sem header/com chave errada; 404 pra
  série fora do catálogo (`selic`); dados conferidos direto via `psql`.
- `project/PHASE.md`, `ARCHITECTURE.md` e `OVERVIEW.md` atualizados refletindo o progresso.

**Estado ao final**: Fase 1, etapas 1.2-1.5 concluídas e validadas ponta a ponta. Próximo passo
é a 1.6 (portar as fontes restantes do catálogo). Trabalho ainda não commitado — falta
confirmar com o dono do projeto antes do push.

### 2026-08-27 — Sessão 3

**Objetivo**: Fase 1.6, primeira fonte adicional — Yahoo Finance (cotação, técnicos,
dividendos, histórico de preço).

**O que foi feito**:
- Escopo confirmado com o dono do projeto via `AskUserQuestion`: portar as 5 capacidades do
  `acoes_yahoo.py` do Anchor de uma vez (não só cotação) — fatia maior que a da Sessão 2, mas
  mesmo padrão de arquitetura (source → service cache-through → schema → router).
- Extraído `_is_fresh` de `macro_series_service.py` pra `app/services/freshness.py`
  (compartilhado com o novo `stock_service.py`), única mudança em código já existente.
- `app/sources/acoes_yahoo.py`: reimplementação das 5 funções do Anchor
  (`fetch_quote`/`fetch_price_history`/`fetch_dividends_avg`/`fetch_technicals`/
  `fetch_dividend_payments`), recebendo um ticker por chamada (não lista, diferente do Anchor
  — nossa API é por-requisição) com um helper HTTP compartilhado.
- 5 tabelas novas (`api/app/models/stock.py`, migration `0002`): `stock_quotes`,
  `stock_technicals`, `stock_dividends_avg` (upsert por sobrescrita) e `stock_price_history`,
  `stock_dividend_payments` (upsert só-insere, fato histórico imutável).
- `app/services/stock_service.py`: dois orquestradores genéricos reaproveitados pelas 5
  capacidades (`_get_or_refresh_single_row`, `_get_or_refresh_list`), mais o tratamento
  especial de `dividends-avg` (estado "sem dado" — 404 só sem cache, senão mantém servindo o
  cache existente).
- 5 rotas sob `GET /v1/stocks/{ticker}/...` (`quote`, `technicals`, `dividends-avg`,
  `price-history`, `dividend-payments`), mesma auth por `X-API-Key`.
- 30 novos testes automatizados (mockados) — cliente Yahoo, service (padrão 1-linha via quote,
  padrão lista-append via price-history, smoke tests dos outros 3) e router — todos passaram
  de primeira, mais os 14 já existentes (44 no total).
- Validado ao vivo contra o Yahoo real (ticker PETR4): cotação R$42,70, técnicos (SMA/CAGR)
  calculados, dividendo médio 5a R$7,88, 2.491 pontos de histórico de preço, 34 pagamentos de
  dividendo; MGLU3 confirmou que `dividends-avg` funciona pra outro ticker; cache confirmado
  (`cached: true` numa segunda chamada de `/quote`); 401 sem header.
- `project/PHASE.md` e `ARCHITECTURE.md` atualizados.

**Estado ao final**: Fase 1.6 com 2 de ~11 fontes portadas (BCB SGS, Yahoo Finance). Próxima
fonte candidata: bolsai (fundamentos de ação BR, mas exige API key própria — diferente das
duas primeiras) ou CVM DFP/FII (dados abertos, sem chave). Trabalho ainda não commitado.

### 2026-08-27/28 — Sessão 4

**Objetivo**: Fase 1.6, terceira fonte — CVM (fundamentos DFP: ROE/payout/DCF; FII: indicadores
mensais + imóveis).

**O que foi feito**:
- Escopo confirmado com o dono do projeto via `AskUserQuestion`: portar `cvm_dfp.py` completo +
  `cvm_fii.py` (não só uma fatia). Antes de planejar em detalhe, baixei e inspecionei os zips
  reais da CVM (DFP e FII) pra confirmar 100% do schema documentado nos docstrings do Anchor
  (formato de `CD_CVM`/`CNPJ_Fundo_Classe`/datas, nomes de coluna) em vez de planejar em cima de
  suposição — zips apagados depois da inspeção.
- Decisão de design central: como a resolução ticker→código-CVM/CNPJ do Anchor depende da
  bolsai (fonte paga, não portada), os 5 endpoints novos recebem **código CVM**/**CNPJ**
  diretamente (não ticker) — `resolve_cnpj` do Anchor não foi portado.
- `api/app/sources/cvm_dfp.py`/`cvm_fii.py`: reimplementação completa (identificadores em
  inglês) — download+cache de zip em disco (`api/.cache/`, gitignored), parsing de CSV
  `;`-delimitado/`latin1`, `_find_exact`/`_find_by_keyword` (D&A/Capex por busca de texto,
  contas sem código padronizado entre empresas), `_effective_tax_rate`, `_nwc_change`,
  normalização de CNPJ (`normalize_cnpj`).
- 5 tabelas novas (`api/app/models/company.py`/`fii.py`, migration `0003`): `company_roe`,
  `company_payout_avg`, `company_dcf_fundamentals` (1 linha por cvm_code, overwrite),
  `fii_monthly_indicators` (1 linha por cnpj, overwrite), `fii_properties` (N linhas por cnpj,
  refresh via delete-e-insere do conjunto inteiro).
- Extraído `app/services/single_row_cache.py` — generaliza o cache-through "1 linha, overwrite"
  que antes só existia dentro de `stock_service.py`; refatorado `stock_service.py` pra usar a
  versão compartilhada (comportamento idêntico, suite de 44 testes da Sessão 3 confirmada sem
  regressão antes de seguir com CVM).
- `app/services/company_service.py` (roe/payout/dcf via helper compartilhado) +
  `app/services/fii_service.py` (monthly_indicators via helper compartilhado; properties com
  lógica própria de delete-e-insere).
- 5 rotas: `GET /v1/companies/{cvm_code}/{roe,payout,dcf-fundamentals}` e
  `GET /v1/fiis/{cnpj}/{monthly-indicators,properties}`, mesma auth por `X-API-Key`.
- 39 novos testes automatizados (mockados) — incluindo `tests/cvm_fixtures.py` (helper que monta
  zip em memória com CSV fiel ao schema real confirmado) — todos passaram de primeira nos
  clientes CVM (14) e services/routers (25); suite completa: 83 testes.
- Validado ao vivo contra a CVM real: VALE3 (CD_CVM 4170) — ROE 6,25%, **alíquota efetiva
  55,75% batendo exatamente com o número citado no docstring original do Anchor pra essa mesma
  empresa** (forte confirmação da lógica portada), payout médio 5a 61,38% (~19s, 5 zips); FII
  CNPJ `00332266000131` — indicador mensal e imóvel (Via Parque Shopping) corretos; 404/401/
  cache confirmados.
- `project/PHASE.md` e `ARCHITECTURE.md` atualizados.

**Estado ao final**: Fase 1.6 com 3 de ~11 fontes portadas (BCB SGS, Yahoo Finance, CVM
DFP+FII). Próxima fonte candidata: bolsai (exige API key própria) ou uma das fontes de cripto
(CoinGecko/DefiLlama/alternative.me/ultrasound.money, todas sem chave). Trabalho ainda não
commitado — falta confirmar com o dono do projeto antes do push.

### 2026-08-28 — Sessão 5

**Objetivo**: Fase 1.6, quarta fonte — cripto (CoinGecko + DefiLlama + alternative.me +
ultrasound.money).

**O que foi feito**:
- Escopo confirmado com o dono do projeto via `AskUserQuestion`: tudo — indicadores de saúde do
  ETH (TVL trend, net issuance, fees vs emissão, NVT ratio), Fear & Greed global, e
  cotação/histórico de qualquer moeda por símbolo.
- Decisão de design central: os 4 indicadores do ETH viram **um endpoint parametrizado por
  código** (`GET /v1/crypto/eth-indicators/{indicator_code}`), reaproveitando o padrão de
  catálogo já usado em `/v1/macro-series/{series_code}` — mais consistente aqui do que "1
  endpoint por capacidade" (padrão Yahoo/CVM) porque as 4 leituras são literalmente o mesmo
  shape (um número), só vindo de fontes HTTP diferentes. Sem a classificação GREEN/RED do
  Anchor (isso é regra de negócio da aplicação, não dado da fonte).
- `app/sources/crypto_common.py` (`CryptoDataError` único, compartilhado pelas 4 fontes) +
  `cripto_defillama.py`/`cripto_ultrasound.py`/`cripto_feargreed.py`/`cripto_coingecko.py`
  (reimplementação das 5 funções do Anchor) + `crypto_indicator_catalog.py` (catálogo travado
  aos 4 códigos já validados em produção).
- **Achado de testabilidade durante a implementação**: o catálogo inicialmente importava as
  funções de fetch direto (`from app.sources.cripto_defillama import fetch_tvl_trend_mom`),
  congelando a referência no dict no momento da construção — `patch()` nos testes não tinha
  efeito nenhum, porque o dataclass já guardava o objeto função original, não um lookup por
  nome. Corrigido trocando pra closures que fazem o lookup do atributo do módulo em tempo de
  chamada (`lambda: cripto_defillama.fetch_tvl_trend_mom()`) — mesma técnica que permite mockar
  função importada sem reescrever a chamada.
- 5 tabelas novas (`api/app/models/crypto.py`, migration `0004`): `crypto_indicators`,
  `crypto_fear_greed` (singleton, `id` sempre 1), `crypto_coin_resolution`, `crypto_quotes` (1
  linha, overwrite) e `crypto_price_history` (append-only).
- Extraído `app/services/append_only_list_cache.py` — generaliza o `_get_or_refresh_list` que
  só existia em `stock_service.py` (2º uso real do shape); `stock_service.py` refatorado pra
  usar a versão compartilhada, suite completa (83 testes) confirmada sem regressão antes de
  seguir com cripto.
- `app/services/crypto_service.py`: indicadores/Fear&Greed via `single_row_cache`; resolução
  símbolo→coin_id com cache próprio (TTL longo), reaproveitado entre `/quote` e
  `/price-history` (confirmado por teste: só 1 chamada de resolução pras duas rotas).
- 4 rotas sob `/v1/crypto/...` (`eth-indicators/{code}`, `fear-greed`, `{symbol}/quote`,
  `{symbol}/price-history`), mesma auth por `X-API-Key`.
- 30 novos testes automatizados (mockados) — todos passaram (após o fix de testabilidade
  acima); suite completa: 113 testes.
- Validado ao vivo contra as 4 APIs reais: TVL trend +21,4%, net issuance +0,86% anualizado,
  fees/emissão 0,015, NVT ratio 0,79 (todos os 4 indicadores do ETH); Fear & Greed 73
  ("Greed"); BTC quote ~US$80.462 e 365 pontos de histórico de preço; cache confirmado
  (`cached: true`); 404 pra indicador e símbolo desconhecidos; 401 sem chave.
- `project/PHASE.md` e `ARCHITECTURE.md` atualizados.

**Estado ao final**: Fase 1.6 com 7 de 11 fontes portadas (BCB SGS já contava fora da 1.6; nesta
fase: Yahoo Finance, CVM DFP+FII, CoinGecko+DefiLlama+alternative.me+ultrasound.money). Restam
4: bolsai (única que exige API key própria), B3 index stats, SEC EDGAR, Yahoo Metais. Trabalho
ainda não commitado — falta confirmar com o dono do projeto antes do push.

### 2026-08-28 — Sessão 6

**Objetivo**: fechar a Fase 1.6 — as últimas 4 fontes do catálogo (B3 index stats, Yahoo
Metais, bolsai, SEC EDGAR).

**O que foi feito**:
- Dois bloqueios de credencial resolvidos no início da sessão: `BOLSAI_API_KEY` (o dono do
  projeto tinha a chave, mas não sabia onde estava salva — encontrada em
  `anchor/data-collector/.env`, copiada pra `api/.env`) e `SEC_EDGAR_CONTACT_EMAIL` (confirmado
  com o dono do projeto). Ambas gitignored, nunca commitadas.
- Escopo confirmado via `AskUserQuestion`: tudo numa fatia só (SEC EDGAR sozinho tem
  complexidade parecida com a CVM — resolução ticker→CIK, fundamentos+DCF+payout, fallback de
  tags — mas o dono do projeto preferiu fechar a fase de uma vez), sem REIT fundamentals
  (capacidade extra do Anchor fora do catálogo original de 12 fontes).
- Achado ao reler `stocks.py` durante o planejamento: `acoes_yahoo.fetch_quote`/
  `fetch_price_history` usam `suffix=".SA"` por padrão e nunca eram chamadas com outro valor —
  `/v1/stocks/{ticker}/...` só serve tickers B3. Por isso SEC EDGAR (mercado americano) ganhou
  namespace próprio (`/v1/us-stocks/{ticker}/...`) em vez de reaproveitar `/v1/stocks/`.
- `api/app/sources/b3_index_stats.py` + `b3_index_catalog.py` (catálogo travado: IFIX/SMLL/IDIV,
  ano-base fixo por índice).
- `api/app/sources/metals_catalog.py` — **sem cliente HTTP novo**, reusa
  `acoes_yahoo.fetch_quote`/`fetch_price_history` direto com `suffix=""` (só um catálogo de 4
  símbolos XAU/XAG/XPT/XPD).
- `api/app/sources/acoes_bolsai.py` (fundamentos BR, expõe `cvm_code` pra encadear com
  `/v1/companies/...`; `roe` exposto como vem da fonte, com ressalva de confiabilidade
  documentada) e `api/app/sources/sec_edgar.py` (fundamentos/DCF/payout US, resolução
  ticker→CIK cacheada, rate limit ~9 req/s portado do Anchor).
- Renomeado `cvm_ttl_seconds` → `fundamentals_ttl_seconds` em `config.py`/`.env`/
  `.env.example`/`companies.py`/`fiis.py` — bolsai e SEC EDGAR reusam o mesmo campo (3º uso da
  mesma semântica: fundamento trimestral/anual).
- 8 tabelas novas (migration `0005`): `b3_index_history`, `metal_quotes`,
  `metal_price_history`, `stock_bolsai_fundamentals`, `sec_edgar_cik_resolution`,
  `us_stock_fundamentals`, `us_stock_dcf_fundamentals`, `us_stock_payout_avg`.
- Serviços: `b3_index_service.py`, `metal_service.py`, `us_stock_service.py` (resolução de CIK
  reaproveitada entre os 3 endpoints, mesmo padrão do `crypto_coin_resolution`), e
  `stock_service.py` ganhou `get_or_refresh_bolsai_fundamentals`.
- 7 rotas novas: `GET /v1/b3-indexes/{index_code}/history`, `GET /v1/metals/{metal_code}/
  {quote,price-history}`, `GET /v1/stocks/{ticker}/bolsai-fundamentals` (no router já
  existente), `GET /v1/us-stocks/{ticker}/{fundamentals,dcf-fundamentals,payout}`.
- 49 novos testes automatizados (mockados) — incluindo o SEC EDGAR com fixtures de tags XBRL
  fiéis ao formato real (duration/instant rows) — todos passaram; suite completa: 162 testes.
- Validado ao vivo contra as 4 APIs reais: IFIX com 3.885 pontos desde 2010; ouro (XAU)
  cotado; bolsai/PETR4 retornando `cvm_code: "9512"` (bate com o CVM); **SEC EDGAR/AAPL com
  payout médio 5a de 15,08% — número real e bem conhecido (a Apple retém a maior parte do lucro
  pra buyback em vez de dividendo)**, forte confirmação da lógica portada; **JPM (banco)
  retornou 404 em `/dcf-fundamentals` como esperado**, confirmando que a lacuna de taxonomia
  bancária documentada pelo Anchor foi reproduzida corretamente; cache/401/404 confirmados em
  todos os endpoints novos.
- `project/PHASE.md`, `ARCHITECTURE.md` e `OVERVIEW.md` atualizados.

**Estado ao final**: **Fase 1.6 completa — as 11 fontes do catálogo original portadas.**
Próximo passo natural: Fase 1.7 (migrar o Anchor pra consumir a Finance API em vez de rodar
`data-collector/main.py` localmente) ou Fase 1.8 (documentação pública da API). Trabalho ainda
não commitado — falta confirmar com o dono do projeto antes do push.

### 2026-08-28 — Sessão 7

**Objetivo**: Fase 1.7 — migrar o Anchor (`../anchor`) pra consumir a Finance API em vez de rodar
`data-collector/main.py` localmente. Confirmado commit da Sessão 6 já estava no repo
(`4072a3e`) antes de começar.

**O que foi feito**:
- 2 agentes `Explore` em paralelo (um por repo) mapearam o contrato completo: toda função de
  `anchor/data-collector/sources/*.py` (assinatura, shape de retorno, chaves de API) de um lado,
  todo endpoint/schema da Finance API do outro. Achado central: **a Finance API não cobre 100% do
  que o Anchor fazia** — cotação/técnicos/dividendos/preço de ticker sem sufixo `.SA` (ação
  US/ETF US/REIT), indicadores imobiliários de REIT, IBOV, e `resolve_cnpj` de FII (nunca
  portada, decisão da Sessão 4) não têm endpoint equivalente.
- Escopo confirmado com o dono do projeto via `AskUserQuestion`: migração **híbrida** — migra o
  que a API já cobre, deixa o resto local, sem estender a API agora (candidato a "Fase 1.6b"
  registrado em `ROADMAP.md`).
- Bug achado na exploração (`GET /v1/fiis/{cnpj}/properties` não captura `FundNotFoundError`) —
  investigado a fundo antes de "corrigir": lendo `fii_service.py` de verdade, a causa não é um
  bug de exceção não capturada, é ambiguidade de fonte — lista vazia serve tanto pra CNPJ
  desconhecido quanto pra FII de papel/recebíveis sem imóvel nenhum, e não dá pra distinguir os
  dois com o dado que a CVM fornece. Confirmado com o dono do projeto: **não mexer**, documentar
  como limitação consciente (`PENDING.md` item P1) — "corrigir" arriscaria classificar um FII de
  papel válido como "não encontrado" na primeira chamada.
- `anchor/data-collector/sources/finance_api_client.py` (módulo novo, repo do Anchor): ~20
  funções-wrapper que replicam a forma exata das funções antigas que substituem, escondendo o
  loop por identificador (Finance API só aceita um por chamada, decisão de design já registrada em
  `ARCHITECTURE.md`) — mantém o corpo das `collect_*` de `main.py` quase intocado.
- Módulos deletados no Anchor (100% redundantes): `bcb_sgs.py`, `cvm_dfp.py`,
  `b3_index_stats.py`, `metais_yahoo.py`, `cripto_defillama.py`, `cripto_ultrasound.py`,
  `cripto_feargreed.py`, `cripto_coingecko.py`. Trimados (só a fatia migrada saiu):
  `acoes_bolsai.py`, `cvm_fii.py`, `sec_edgar.py`.
- **2 bugs achados e corrigidos durante a validação ao vivo** (não durante o planejamento):
  (1) primeira versão do `finance_api_client.py` capturava `FinanceApiError` genérico dentro do loop
  por-ticker — rodando com a Finance API derrubada de propósito (`docker compose stop api`), o
  coletor terminava `exit 0`/"Updated 0 quote(s)" em vez de falhar alto, mascarando
  indisponibilidade total como "sem dado nenhum". Corrigido pra só capturar 404
  (`FinanceApiNotFoundError`) dentro do loop, erro de rede/5xx propaga. (2) `/v1/metals/{code}` e
  `/v1/b3-indexes/{code}` usam catálogo minúsculo (`xau`, `ifix`), Anchor sempre trabalhou
  maiúsculo — `.lower()` só na URL, sem mudar o ticker gravado no SQLite dele. (3) códigos dos 4
  indicadores ETH usam hífen (`tvl-trend`), Anchor usa underscore internamente (`tvl_trend`,
  chave de `indicator_thresholds`) — corrigido nos call sites, sem tocar no schema do Anchor.
- Validado ao vivo, ponta a ponta, contra a Finance API real (`docker compose up`) e o
  `anchor.db` real: `--ticker PETR4`/`MGLU3`, `crypto` (4 indicadores ETH), `--crypto-ticker
  BTC`, `--metal-ticker XAU`, `--benchmark-returns` (7 benchmarks), `--fii-cvm-data`, `--us-ticker
  AAPL` (payout 15,08%, mesmo número confirmado na Sessão 6). Confirmado que o que ficou local
  segue funcionando sem a Finance API: `--reit-ticker`, `--etf-us-ticker`, `--fii-resolve-cnpj`.
  Suíte da Finance API: 162/162 (sem regressão, nenhum endpoint tocado).
- `project/PENDING.md`, `PHASE.md`, `ROADMAP.md` (aqui) e `project/SESSIONS.md` do Anchor
  (Sessão 88, relato completo da migração do lado dele) atualizados.

**Estado ao final**: Fase 1.7 completa (migração híbrida). Próximo passo natural: Fase 1.8
(documentação pública da API) ou, no Anchor, considerar a "Fase 1.6b" registrada em
`ROADMAP.md` se algum consumidor futuro precisar do que ficou de fora. Commitado e pushado nos
dois repos (`easybusiness` `4072a3e..7735289`, `anchor` `6384992..d49301e`, depois de uma
correção de nome — ver Sessão 8).

### 2026-08-29 — Sessão 8

**Objetivo**: renomear "Super API"/"Super DB" (nome que grudou por engano, sugeria escopo maior
que o real) pra "Finance API"/"Finance DB"; depois, Fase 1.8 — documentação pública.

**O que foi feito — renomeação**:
- Escopo confirmado com o dono do projeto via `AskUserQuestion`: renomear em todo lugar,
  incluindo o histórico já commitado do `SESSIONS.md` (Sessões 1-7) — não é reescrita de git
  history (nenhum commit alterado/rebased), só um commit novo corrigindo texto. `Super Banco de
  Dados`/`Super DB` corrigido junto, pro mesmo motivo.
- `easybusiness`: prosa em `README.md`, `api/app/main.py` (título do FastAPI), 1 comentário em
  `api/app/sources/crypto_indicator_catalog.py`, e todo `project/` (incluindo as 6 sessões já
  commitadas do `SESSIONS.md`). Nenhum identificador de código precisou mudar aqui.
- `anchor`: `sources/super_api_client.py` renomeado pra `sources/finance_api_client.py`,
  `SuperApiError`/`SuperApiNotFoundError` → `FinanceApiError`/`FinanceApiNotFoundError`,
  `SUPER_API_BASE_URL`/`SUPER_API_KEY` → `FINANCE_API_*` (`.env`/`.env.example`), mais prosa em
  `main.py`/`README.md`/docstrings dos módulos trimados/`project/SESSIONS.md` (Sessão 88, ainda
  não commitada nessa hora).
- Validado: `grep` confirmando zero ocorrência residual nos dois repos, recompilação Python
  limpa, smoke test ao vivo (`--ticker PETR4`, `crypto`) contra a Finance API real, suíte da API
  162/162.
- Commitado (não amend) e pushado: `easybusiness` `ea46e5b..7735289`, `anchor` — nasceu direto
  com o nome certo, um commit único `d49301e` (nada tinha sido commitado lá ainda).

**O que foi feito — Fase 1.8 (documentação pública)**:
- Padrão do TruthID esclarecido pelo dono do projeto (eu tinha presumido Docusaurus, errado): é
  `site/frontend`, Next.js (App Router) + Fumadocs, com conta de usuário (Rails/OAuth) e 4
  idiomas via `next-intl` + i18n do próprio Fumadocs. Explorado a fundo (1 agente `Explore`)
  pra separar o que é carga real do que é bloat específico do TruthID antes de desenhar o
  equivalente do EasyBusiness.
- Escopo fechado com o dono do projeto via várias rodadas de `AskUserQuestion`: **inglês, sem
  i18n** (`GUIDELINES.md` já dizia que documentação de API pública é em inglês — eu tinha
  presumido português por engano, corrigido antes de codar); **sem conta/backend**, só docs;
  componente novo `docs/` na raiz do monorepo (não repo separado); **referência de endpoint
  auto-gerada via `fumadocs-openapi`** a partir do `/openapi.json` da própria FastAPI (não
  hand-written como o TruthID faz pros SDKs — já são 30 endpoints crescendo toda sessão, hand-
  written desatualizaria rápido); serviço novo no `docker-compose.yml`, dev mode, mesmo padrão
  do TruthID; sem deploy público ainda.
- `docs/`: Next.js 16 + React 19 + Tailwind v4 + `fumadocs-core`/`fumadocs-mdx`/`fumadocs-ui`/
  `fumadocs-openapi`, sem `next-intl`. `lib/source.ts` (`defineDocs`+`loader`, sem `i18n` key —
  mais simples que o do TruthID), `app/docs/[[...slug]]/page.tsx`+`layout.tsx` únicos (sem o
  split `app/docs` vs `app/[locale]/docs` que o TruthID só precisa pro export estático do
  GitHub Pages), busca embutida (`fumadocs-core/search/server`, Orama, zero serviço externo).
  Marca própria (emerald, não copiado do teal/cyan do TruthID).
- Conteúdo em inglês: `index.mdx`/`quickstart.mdx` + 4 páginas de conceito
  (`auth`/`caching`/`catalog`/`errors`) escritas à mão, cobrindo o envelope `cached`/`stale`/
  `fetched_at`, TTLs por tipo de dado (`config.py`), a tabela fonte→endpoint (reaproveitando
  `CONTEXT.md`), e os 3 modos de erro (404 catálogo desconhecido vs 404 sem dado vs 502 fonte
  fora do ar) incluindo a ressalva documentada de `/v1/fiis/{cnpj}/properties` (`PENDING.md`
  P1).
- **`scripts/generate-reference.mjs`**: roda no `predev`/`prebuild`, busca
  `{API_BASE_URL}/openapi.json` (default `http://api:8000`, hostname do compose) com retry (10
  tentativas/2s, cobre o `api` ainda não estar pronto), chama `generateFiles` do
  `fumadocs-openapi` — `content/docs/reference/` é gitignored, nunca commitado, sempre
  regenerado.
- **3 bugs reais achados só rodando de verdade** (documentação oficial não bastou sozinha —
  achada via `gh search code` no repo `fuma-nama/fumadocs` depois de tentativa e erro):
  (1) `createOpenAPIPage()` não pode ser chamado direto num módulo alcançável por um Server
  Component (`components/mdx.tsx`, importado pelo `page.tsx`) — isolado num
  `components/openapi-page.tsx` próprio com `"use client"`; (2) as páginas de referência
  geradas quebravam com `Cannot read properties of undefined (reading 'bundled')` — faltava o
  `page.tsx` chamar `openapi.preloadOpenAPIPage(page)` e mesclar o resultado nas props do
  `OpenAPIPage` (a documentação do próprio `fumadocs-openapi`, achada via `gh search code`,
  confirmou o wiring exato — `openapi.loaderPlugin()` que eu tinha tentado primeiro era coisa
  cosmética, não a causa); (3) `docker-compose.yml` copiado com `user: "1000:1000"` (padrão do
  serviço `api`) quebrava `npm install` com `EACCES` no volume nomeado de `node_modules` (nasce
  root-owned) — removido, confirmado que o `frontend` do próprio TruthID também não usa isso.
- Validado ao vivo, ponta a ponta, via `docker compose up --build` de verdade (não só localmente
  fora do Docker): API sobe, `docs` gera a referência contra `http://api:8000/openapi.json`
  (hostname interno do compose, não `localhost`), `next build` compila as 34 páginas sem erro,
  `/docs`, uma página de referência real (`get_macro_series_...`, conteúdo correto renderizado),
  páginas de conceito, e `/api/search` respondendo 200 com índice real.
- `README.md`, `project/PHASE.md` (1.8 fechada, **Fase 1 completa**) e `project/OVERVIEW.md`
  atualizados.

**Estado ao final**: Fase 1 do EasyBusiness **completa** (8/8 etapas). Próximo passo natural:
Fase 2 (Engine Fiscal/SEFAZ) do blueprint original, ou considerar a "Fase 1.6b" registrada em
`ROADMAP.md` se um consumidor futuro precisar do que ficou fora da migração híbrida do Anchor.
Commitado e pushado (`ea46e5b..af59ff3`).

### 2026-08-29 — Sessão 9

**Objetivo**: pedido explícito do dono do projeto — deploy público dos docs no GitHub Pages
(1.9, item que a Sessão 8 tinha deixado deliberadamente de fora do escopo).

**O que foi feito**:
- Escopo fechado via `AskUserQuestion`: subpath padrão do GitHub Pages
  (`masterlxz.github.io/easybusiness/docs/`), sem domínio próprio.
- `next.config.ts`: export estático condicional — `output: "export"` + `basePath` só quando
  `NEXT_BASE_PATH` está setada (mesmo padrão do TruthID); sem a env var (dev/docker-compose),
  comportamento dinâmico intocado.
- **Achado de design antes de codar**: gerar a referência de endpoints em CI precisa do schema
  OpenAPI, mas a API não está deployada publicamente (self-host, MVP) — rodar Postgres+API
  inteiros só pra isso no CI seria desproporcional. Confirmado que dá pra evitar: `app.openapi()`
  é reflexão pura sobre rotas/schemas Pydantic (sem I/O), e `create_engine()`
  (`api/app/database.py`) nunca conecta de fato na importação — só valida o dialeto/driver. Um
  `DATABASE_URL` placeholder basta pra importar `app.main` e gerar o schema sem banco nenhum.
  **Verificado antes de commitar**: schema gerado com placeholder é **idêntico byte-a-byte** ao
  gerado contra a API real rodando (`diff` limpo).
- `scripts/generate-reference.mjs`/`lib/openapi.ts` ganharam um segundo modo
  (`OPENAPI_SCHEMA_PATH`, lê de um arquivo local) ao lado do modo HTTP existente — mesma lógica
  de resolução nos dois arquivos, já que o "document" embutido no MDX gerado precisa bater com o
  que `openapi.preloadOpenAPIPage()` resolve depois, do jeito que a Sessão 8 já tinha desenhado.
- `.github/workflows/deploy-docs.yml` (novo, mesmo padrão do TruthID —
  `actions/checkout`→build→`actions/deploy-pages`, sem o passo de remoção de rotas nem o repo
  APT que o deles tem, porque o EasyBusiness não tem conta de usuário nem instalador nativo):
  gera o snapshot do schema (passo Python, `DATABASE_URL` placeholder), builda o export estático
  (`NEXT_BASE_PATH=/easybusiness`, `OPENAPI_SCHEMA_PATH=./openapi.json`), publica via
  `actions/upload-pages-artifact`+`actions/deploy-pages`. Dispara em push tocando `docs/`,
  `api/app/`, `api/requirements.txt`, ou o workflow em si.
- GitHub Pages habilitado no repo via `gh api repos/masterlxz/easybusiness/pages -X POST -f
  build_type=workflow` (não tinha Pages nenhum configurado antes).
- Validado ao vivo, localmente, antes do push: `npm run build` com `NEXT_BASE_PATH=/easybusiness`
  e `OPENAPI_SCHEMA_PATH` de verdade — todo link/asset/favicon no HTML gerado (`out/`) já sai
  prefixado `/easybusiness/...` corretamente, uma página de referência real com conteúdo
  renderizado, índice de busca virou arquivo estático (`out/api/search`). Achado no caminho, sem
  relação com a feature em si: rodar o container `docs` (dev mode) e depois testar `next build`
  local no host deixa `node_modules`/`.next`/`content/docs/reference`/`next-env.d.ts` root-owned
  no bind mount (mesmo motivo de sempre — o container roda sem `user: "1000:1000"`, ver Sessão 8)
  — limpo via `docker run --rm -v ... node:20-bookworm-slim rm -rf ...` em vez de precisar de
  `sudo` no host.
- `README.md` (link pro site publicado) e `project/PHASE.md` (nova etapa 1.9) atualizados.

**Estado ao final**: docs publicados (workflow criado, Pages habilitado, primeiro deploy dispara
no próximo push que tocar `docs/`). Trabalho ainda não commitado — falta confirmar com o dono do
projeto antes do push.

### 2026-08-29 — Sessão 10

**Objetivo**: pedido do dono do projeto, feito do lado do Anchor — apagar `data-collector/` de
vez, rodando a versão free/self-hosted da Finance API "já instalada" localmente (sem setup
manual, sem Docker/Postgres pro usuário final) e deixando um espaço de configuração pra uma
futura instância Cloud paga do EasyBusiness. Sessão cross-repo: planejamento completo (2 agentes,
`Explore`/`Plan`) feito do lado do Anchor, cobrindo os dois repos; implementação de código real
só do lado EasyBusiness (Fase 1.10 — a fatia menor, autocontida, que desbloqueia o resto).

**O que foi feito**:
- **Decisão de empacotamento**, confirmada com o dono via `AskUserQuestion`: binário compilado
  (mesmo padrão PyInstaller que `data-collector/` já usa no Anchor desde a Fase 11.3 dele), não
  Docker Compose gerenciado pelo Anchor nem lib pip — motivo: zero dependência de Docker pro
  usuário final de um app desktop público, zero pasta Python no Anchor, mecanismo já provado
  neste exato par de repos.
- Levantamento antes de codar: confirmado que `api/app/database.py`/`config.py`/`auth.py` já
  são inteiramente dialect/env-agnósticos (nenhuma mudança neles foi necessária) — o único
  obstáculo real pra rodar contra SQLite eram 3 arquivos usando
  `sqlalchemy.dialects.postgresql.insert` explicitamente.
- `app/services/db_dialect.py` (novo): dispatcher que escolhe `sqlalchemy.dialects.sqlite.insert`
  ou `...postgresql.insert` a partir do dialeto da conexão em runtime — API idêntica nos dois
  (`on_conflict_do_update`/`on_conflict_do_nothing`, mesmo `.excluded`), SQLite ≥3.24 suporta
  `ON CONFLICT` nativo. Trocado em `single_row_cache.py`, `append_only_list_cache.py`,
  `macro_series_service.py` — os 3 únicos pontos Postgres-specific do código (confirmado via
  grep em `models/`/`migrations/versions/` que não há mais nenhum).
- `api/sidecar_main.py` (novo): entrypoint separado do `uvicorn app.main:app` normal — roda
  Alembic programaticamente até `head` antes de servir (mesmo histórico de migrations do path
  Postgres, evolui um db local existente entre versões do app consumidor, ao contrário de
  `Base.metadata.create_all()`), sobe uvicorn passando o objeto `app` importado direto (não a
  string `"app.main:app"` — binário PyInstaller-frozen não resolve import dinâmico do jeito que
  o reload/multi-worker do uvicorn espera), porta OS-assigned (ou `PORT` do env) anunciada via
  `SIDECAR_PORT=<porta>` na primeira linha do stdout — sinal de prontidão pro processo
  embutidor (Anchor, ainda não desenhado — Fase 14.2 dele).
- `api/requirements-sidecar-build.txt` (novo, só `pyinstaller`, mesmo padrão do
  `requirements-build.txt` do `data-collector/` do Anchor).
- **Validado ao vivo, não só em teoria**: instalado `api/requirements.txt` num venv descartável,
  rodado `sidecar_main.py` interpretado contra `sqlite:////tmp/...db` — Alembic criou as 22
  tabelas das 5 migrations, `/healthz` respondeu 200, `/v1/macro-series/cdi` e `/ipca` fizeram
  fetch real na API do BCB SGS e fizeram upsert de verdade no SQLite (exercitando o dialect fix
  de ponta a ponta, não só import). Repetido depois com `pyinstaller --onefile` de verdade (não
  só o script) — binário compilado subiu e respondeu igual. `docker compose exec api pytest -v`
  (suite completa, path Postgres) continua 162/162 depois do refactor do dialeto — sem
  regressão.
- Planejamento do restante (não implementado agora, registrado pra sessões futuras): Fase 1.11
  do EasyBusiness (fechar o gap de 4 capacidades da antiga "1.6b" — ver `ROADMAP.md`) e Fase 14
  do Anchor (CI que builda/embute o sidecar via checkout do easybusiness num ref fixado, lifecycle
  do processo + client HTTP em Rust, Settings Local/Remote, porta do fetch+write Python→Rust por
  classe de ativo, limpeza final do `data-collector/`) — desenho completo no `PHASE.md` do Anchor,
  não reproduzido aqui.

**Estado ao final**: Fase 1.10 completa e validada ao vivo (interpretado + compilado). Nenhum
código do lado Anchor foi tocado ainda — decisão explícita do dono do projeto de escopar esta
sessão só na fatia menor/autocontida. Trabalho ainda não commitado — falta confirmar com o dono
do projeto antes do commit/push.

### 2026-08-29 — Sessão 11

**Objetivo**: pedido feito do lado do Anchor, continuando de onde a Sessão 91 dele parou — fechar
a Fase 1.11 (as 4 capacidades sem endpoint equivalente que a migração híbrida, Fase 1.7, tinha
deixado local no `data-collector/` do Anchor). Sessão cross-repo, implementação toda do lado
EasyBusiness; commit `b4aa8d1`.

**O que foi feito** (3 sub-fatias, todas verificadas ao vivo antes de fechar):
- **1.11.1** — cotação/técnicos/dividendos/histórico de preço/proventos pra ticker sem sufixo
  `.SA` (ação americana comum, ETF-US, REIT, índices sem sufixo tipo IBOV/`^BVSP`):
  `acoes_yahoo.py` já aceitava `suffix=""` desde a Fase 1.6, só faltava a camada de API por cima
  — `models`/`services`/`schemas`/`routers` de `us_stock` ganharam 5 tabelas novas e 5 endpoints
  sob `/v1/us-stocks/{ticker}/quote,technicals,dividends-avg,price-history,dividend-payments`.
  IBOV não ganhou endpoint próprio — passa pelos mesmos, mesma decisão que o `data-collector` do
  Anchor já tomava (`collect_us_price_history(["^BVSP"])` reaproveitando a função genérica).
- **1.11.2** — indicadores imobiliários de REIT via SEC EDGAR (`fetch_reit_fundamentals`
  portado pro `sec_edgar.py`), `GET /v1/us-stocks/{ticker}/reit-fundamentals`. Tabela nova
  `reit_fundamentals` é time-series (append-only, `get_or_refresh_list` reaproveitado com o ano
  no lugar da data), não single-row — a resposta é a série histórica completa.
- **1.11.3** — resolução ticker→CNPJ de FII: `acoes_bolsai.fetch_fii_summary` +
  `cvm_fii.resolve_cnpj` portados do Anchor, `GET /v1/fiis/resolve/{ticker}` (router separado do
  `{cnpj}`-prefixado existente, sem colisão de rota). **Achado real corrigido antes de fechar**:
  o arquivo `geral` da CVM devolve o CNPJ do fundo pontuado (18 caracteres), mas a coluna nova é
  `String(14)` (só dígitos) — sem normalizar, o insert quebrava com `StringDataRightTruncation`.
  Confirmado ao vivo contra HGLG11 real, que hoje responde como "PÁTRIA LOG" (não mais "CSHG
  Logística" — o fundo trocou de administrador/nome desde a implementação original no Anchor).
- **Verificado ao vivo**: AAPL (5 endpoints do 1.11.1), `^BVSP`/IBOV (quote + 2483 pregões de
  histórico), Realty Income e Simon Property (REIT, incluindo o fallback `NetIncomeLoss`→
  `ProfitLoss` da Simon Property), HGLG11 (resolução real, cache confirmado na 2ª chamada). Suite
  completa **196/196** sem regressão.

**Estado ao final**: Fase 1.11 completa — desbloqueia o resto da Fase 14.4 do Anchor
(`main_us_stock`/`main_reit`/`main_etf_us`, benchmarks, `resolve_fii_cnpj`), que fechou na sessão
seguinte do lado dele (ver `SESSIONS.md` do Anchor, Sessão 92).

### 2026-09-16 — Sessão 13

**Objetivo**: pendência antiga (registrada na Sessão 11 quando o dono do projeto decidiu trocar
o nome) — renomear o projeto/produto "EasyBusiness" para "Lume". Escopo confirmado com o dono
do projeto antes de mexer, por ser mudança de grande superfície (repositório público no GitHub,
URL do GitHub Pages, credenciais do Postgres local).

**O que foi feito**:
- Trocadas as referências vivas ao nome antigo: título/prosa em `README.md` e
  `project/{CONTEXT,INDEX,OVERVIEW,ROADMAP}.md`, título do FastAPI (`api/app/main.py`),
  User-Agent dos 4 clientes HTTP (`api/app/sources/{bcb_sgs,acoes_yahoo,b3_index_stats,
  sec_edgar}.py`), nome do projeto Compose + credenciais do Postgres local em
  `docker-compose.yml`, `NEXT_BASE_PATH` no workflow `deploy-docs.yml`, e nome do pacote npm em
  `docs/package.json`/`package-lock.json`. Convenção adotada: "Lume" (capitalizado) em prosa/
  nome de exibição, "lume" (minúsculo) em slugs/paths — mesmo padrão já usado pros projetos
  irmãos (`Anchor`/`anchor`).
- **Decisão consciente**: `SESSIONS.md` e `PHASE.md` ficaram de fora — são log histórico do que
  aconteceu sob o nome antigo, não documentação viva; reescrever mudaria o registro do que
  realmente aconteceu em cada sessão passada.
- Volumes Docker locais antigos (`easybusiness_db-data`, `easybusiness_docs-node-modules`)
  removidos (dev local, descartável) — próximo `docker compose up` recria do zero sob o novo
  nome de projeto Compose (`lume`).
- Commit `76bca07` (não amend), push pro remote.
- Repositório GitHub renomeado `masterlxz/easybusiness` → `masterlxz/lume` (via `gh repo rename`,
  GitHub redireciona o nome antigo por um tempo), remote local atualizado
  (`git remote set-url origin`). Diretório local renomeado
  (`~/Documents/workspace/easybusiness` → `~/Documents/workspace/lume`).
- Validado ao vivo: `docker compose config` (compose file válido depois do rename),
  `gh repo view masterlxz/lume` (rename confirmado), workflow `deploy-docs.yml` disparado pelo
  push (o próprio arquivo mudou, está no path trigger) rodou verde, e
  `https://masterlxz.github.io/lume/docs/` responde 200 (URL nova do GitHub Pages já no ar).

**Estado ao final**: rename completo — código, docs vivos, repo remoto, diretório local e Pages
público todos sob "Lume". Pendência da memória (`pending_rename_lume.md`) removida por
resolvida. Sem impacto em `SESSIONS.md`/`PHASE.md` (histórico preservado) nem nos 3 itens de
brainstorm da Sessão 11 (câmbio multi-moeda, Selic/DI futuro, gestão de opções — continuam sem
pesquisa de fontes, ver `ROADMAP.md`).
