## Fases Detalhadas

### Fase 1 — Finance API + Finance DB (MVP)

**Objetivo**: centralizar, num único serviço confiável, a coleta de dados financeiros que hoje
o Anchor faz de forma isolada (`data-collector/`), expondo tudo via uma API HTTP/JSON — ver
`CONTEXT.md` para o PRD completo e o catálogo de fontes herdado do Anchor.

**Etapas**:
- [x] 1.1 — Setup do repositório (Sessão 1: GitHub criado, `project/` criado com o blueprint incorporado)
- [x] 1.2 — Stack decidida (Sessão 2): Python + FastAPI, PostgreSQL, self-host via Docker Compose
- [x] 1.3 — Schema inicial via Alembic: `macro_series_monthly` (series_code, reference_month, value_pct, source, fetched_at) — `api/app/models/macro_series.py`
- [x] 1.4 — Primeira fonte portada (Sessão 2): BCB SGS (CDI e IPCA), reimplementada em `api/app/sources/bcb_sgs.py`, validada ao vivo contra a API real (481 pontos de CDI desde 1986, 559 de IPCA)
- [x] 1.5 — Contrato definido e validado: `GET /v1/macro-series/{series_code}` com auth por `X-API-Key`, cache-through com TTL configurável (`api/app/services/macro_series_service.py`)
- [x] 1.6 — Portar as fontes restantes do catálogo, uma a uma (11/11 portadas — Fase 1.6 completa)
  - [x] Yahoo Finance (Sessão 3): cotação, técnicos (SMA/CAGR), dividendo médio 5a, histórico de preço, histórico de pagamentos — `api/app/sources/acoes_yahoo.py`, 5 endpoints sob `/v1/stocks/{ticker}/...`, validado ao vivo (PETR4/MGLU3)
  - [x] CVM DFP + FII (Sessão 4): ROE, payout médio 5a, 9 campos do DCF (empresas, por código CVM) + indicadores mensais e imóveis (FII, por CNPJ) — `api/app/sources/cvm_dfp.py`/`cvm_fii.py`, 5 endpoints sob `/v1/companies/{cvm_code}/...` e `/v1/fiis/{cnpj}/...`, validado ao vivo (VALE3/CD_CVM 4170, FII CNPJ 00332266000131)
  - [x] Cripto — CoinGecko + DefiLlama + alternative.me + ultrasound.money (Sessão 5): 4 indicadores de saúde do ETH (TVL trend, net issuance, fees vs emissão, NVT ratio) via catálogo parametrizado, Fear & Greed global, cotação/histórico de qualquer moeda por símbolo — `api/app/sources/cripto_*.py`, 4 endpoints sob `/v1/crypto/...`, validado ao vivo (indicadores reais do ETH, BTC quote+365 pontos de histórico)
  - [x] B3 index stats + Yahoo Metais + bolsai + SEC EDGAR (Sessão 6): histórico de índices B3 (IFIX/SMLL/IDIV, catálogo travado), cotação/histórico de metais preciosos (reaproveita `acoes_yahoo.py` sem cliente HTTP novo), fundamentos bolsai (ticker BR, chave própria), fundamentos/DCF/payout SEC EDGAR (ticker US, resolução CIK cacheada) — 7 endpoints novos sob `/v1/b3-indexes/...`, `/v1/metals/...`, `/v1/stocks/{ticker}/bolsai-fundamentals` e `/v1/us-stocks/...`, validado ao vivo (IFIX 3.885 pontos, ouro, PETR4 via bolsai, AAPL fundamentos/DCF/payout, JPM 404 esperado — banco sem taxonomia compatível)
- [x] 1.7 — Anchor passa a consumir a Finance API em vez de rodar `data-collector/main.py` localmente (Sessão 7, migração **híbrida**): tudo que a Finance API já cobre migrou pra HTTP (`anchor/data-collector/sources/finance_api_client.py`, módulo novo) — ação BR (cotação/técnicos/dividendos/histórico/proventos/fundamentos+DCF), CDI/IPCA, IFIX/SMLL/IDIV, FII (indicadores+imóveis), os 4 indicadores ETH + Fear&Greed + cotação/histórico de cripto, os 4 metais, fundamentos/DCF/payout de ação americana comum. Ficou local, sem endpoint equivalente na Finance API: cotação/técnicos/dividendos/preço de ticker sem sufixo `.SA` (US/ETF/REIT), REIT fundamentals, IBOV, `resolve_cnpj` de FII — candidatos a uma "Fase 1.6b" futura (ver `ROADMAP.md`). Bug achado nesta sessão em `/v1/fiis/{cnpj}/properties` (não distingue CNPJ desconhecido de FII sem imóvel) registrado como pendência consciente, não corrigido — ver `PENDING.md` item P1. Detalhes completos da migração (mapeamento função-por-função, achados de casing/exceção) no `SESSIONS.md` do Anchor, Sessão 88.
- [x] 1.8 — Documentação pública da API (Sessão 7): componente novo `docs/` — Next.js (App Router) +
  Fumadocs, mesmo padrão do TruthID (`site/frontend`, esclarecido nesta sessão: não é Docusaurus)
  mas bem mais enxuto (sem i18n/next-intl — inglês único, conforme `GUIDELINES.md`; sem conta/
  backend, que é conversa de Fase 4). Conteúdo em inglês: `index`/`quickstart` + 4 páginas de
  conceitos (`auth`/`caching`/`catalog`/`errors`) escritas à mão; a referência de cada endpoint
  (`content/docs/reference/`) é **gerada**, não commitada — `scripts/generate-reference.mjs` roda
  no `predev`/`prebuild` via `fumadocs-openapi`, lendo o `/openapi.json` que a FastAPI já expõe de
  graça, pra nunca ficar desatualizada conforme a API cresce. Novo serviço `docs` no
  `docker-compose.yml` (porta 3000, dev mode, mesmo padrão bind-mount + `npm run dev` do TruthID —
  inclusive sem `user: "1000:1000"`, pelo mesmo motivo que o `frontend` deles não tem: o volume
  nomeado de `node_modules` nasce root-owned). Busca embutida do Fumadocs (`/api/search`, Orama,
  zero serviço externo). Sem deploy público ainda (self-host, mesmo estágio da própria API).
  Validado ao vivo via `docker compose up --build` de ponta a ponta (não só localmente): API
  sobe, `docs` gera a referência contra `http://api:8000/openapi.json`, `next build` compila as
  34 páginas sem erro, `/docs`/`/docs/reference/...`/`/docs/concepts/...`/busca respondem 200 com
  conteúdo real. **Fase 1 completa.**
- [x] 1.9 — Deploy público dos docs no GitHub Pages (Sessão 8, mesmo dia): pedido explícito do
  dono do projeto, subpath padrão do GitHub Pages (`https://masterlxz.github.io/easybusiness/docs/`,
  sem domínio próprio). `next.config.ts` ganhou export estático condicional (`output: "export"` +
  `basePath` só quando `NEXT_BASE_PATH` está setada — dev/docker-compose continuam dinâmicos, sem
  mudança). `.github/workflows/deploy-docs.yml` (mesmo padrão do TruthID: `actions/checkout` →
  build → `actions/deploy-pages`) gera um snapshot do schema OpenAPI **sem precisar de banco nem
  API rodando** — `app.openapi()` é reflexão pura sobre rotas/schemas Pydantic, `create_engine()`
  nunca conecta de fato, então um `DATABASE_URL` placeholder basta só pra importar `app.main`
  (confirmado idêntico byte-a-byte contra o schema real antes de commitar essa abordagem).
  `scripts/generate-reference.mjs`/`lib/openapi.ts` ganharam um segundo modo
  (`OPENAPI_SCHEMA_PATH`, arquivo local) ao lado do HTTP existente, sem mudar o comportamento de
  dev. GitHub Pages habilitado no repo via `gh api repos/.../pages` (`build_type: workflow`).
  Validado ao vivo antes do push: build estático local com `NEXT_BASE_PATH=/easybusiness` — todo
  link/asset/favicon no HTML gerado já sai prefixado `/easybusiness/...` corretamente, página de
  referência real renderizada, índice de busca virou arquivo estático.
- [x] 1.10 — Modo SQLite "free/local" (Sessão 10): pedido do dono do projeto pra fechar o
  ciclo Open-Core registrado em `ROADMAP.md` — o Anchor precisa rodar a Finance API localmente
  sem Docker/Postgres, "já instalada", como binário sidecar compilado (mesmo mecanismo que
  `data-collector/` já usa no Anchor desde a Fase 11.3 dele). Achados os 3 únicos pontos
  Postgres-specific do código (`single_row_cache.py`/`append_only_list_cache.py`/
  `macro_series_service.py`, todos `sqlalchemy.dialects.postgresql.insert` com
  `on_conflict_do_*`) — resolvidos com um dispatcher de dialeto (`app/services/db_dialect.py`)
  que troca pra `sqlalchemy.dialects.sqlite.insert` em runtime (API idêntica nos dois dialetos,
  SQLite ≥3.24 suporta `ON CONFLICT` nativo). Nenhuma outra parte do código (`models/`,
  migrations Alembic) tinha algo Postgres-only. Novo `api/sidecar_main.py`: roda as migrations
  Alembic programaticamente até `head` (mesmo histórico do path Postgres, evolui um db local
  existente entre versões do app, ao contrário de `create_all()`), sobe uvicorn passando o objeto
  `app` direto (não a string `"app.main:app"` — binário PyInstaller-frozen não resolve import
  dinâmico), porta OS-assigned anunciada via `SIDECAR_PORT=<porta>` na primeira linha do stdout
  (sinal de prontidão pro processo que embutir o sidecar — Anchor, Fase 14.2 dele, ainda não
  desenhada). `DATABASE_URL`/`API_KEYS` continuam simples env vars, zero mudança em
  `config.py`/`auth.py`. Validado ao vivo: script interpretado E binário compilado
  (`pyinstaller --onefile`) rodando de verdade contra SQLite, Alembic criou as 22 tabelas das 5
  migrations, `/healthz` e `/v1/macro-series/{cdi,ipca}` responderam 200 com fetch real da BCB
  SGS + upsert de verdade no SQLite (não mock). Suite completa (`docker compose exec api pytest`,
  path Postgres) continua 162/162 depois do refactor do dialeto — sem regressão. Fecha só a
  camada de empacotamento; o consumo pelo Anchor (CI, lifecycle do sidecar, migração do
  fetch+write) fica pra sessões futuras, roadmap completo na Fase 14 do `PHASE.md` do Anchor.
- [x] 1.11 — Fecha a lacuna deixada pela migração híbrida (1.6b, ver `ROADMAP.md`): as 4
  capacidades que sobraram locais no `data-collector/` do Anchor por falta de endpoint
  equivalente. **1.11.1** — cotação/técnicos/dividendos/histórico de preço/proventos pra
  ticker sem sufixo `.SA` (ação americana, ETF-US, REIT, índices tipo IBOV): `acoes_yahoo.py`
  já aceitava `suffix=""`, só faltava a camada de API (`models/services/schemas/routers` de
  `us_stock`, 5 tabelas novas) — 5 endpoints novos sob `/v1/us-stocks/{ticker}/...`. IBOV
  (`^BVSP`) não ganhou endpoint próprio — passa pelos mesmos endpoints, mesma decisão que o
  `data-collector` do Anchor já tomava. **1.11.2** — indicadores imobiliários de REIT via SEC
  EDGAR (`fetch_reit_fundamentals` portado, endpoint `/v1/us-stocks/{ticker}/reit-fundamentals`):
  tabela `reit_fundamentals` é time-series (append-only por `reference_year`, não overwrite),
  reaproveitando o helper genérico de lista já existente (`get_or_refresh_list`) com o ano no
  lugar da data — resposta é a série completa, batendo com o jeito que o Rust do Anchor já lê
  essa tabela hoje (lista ordenada por `fetched_at`, não só a mais recente). **1.11.3** —
  resolução ticker→CNPJ de FII (`acoes_bolsai.fetch_fii_summary` + `cvm_fii.resolve_cnpj`
  portados, endpoint `GET /v1/fiis/resolve/{ticker}`, router separado do `{cnpj}`-prefixado
  existente por não ter colisão de rota). **Achado real, corrigido antes de fechar**: o arquivo
  `geral` da CVM devolve o CNPJ do fundo pontuado (18 caracteres), mas a coluna nova é
  `String(14)` (só dígitos) — sem normalizar, o insert quebrava com
  `StringDataRightTruncation` ao testar ao vivo contra HGLG11 real (que hoje responde como
  "PÁTRIA LOG", não mais "CSHG Logística" — fundo trocou de administrador/nome desde a
  implementação original do Anchor). Verificado ao vivo contra AAPL (5 endpoints 1.11.1),
  `^BVSP`/IBOV (quote + price-history, 2483 pregões), Realty Income e Simon Property (REIT,
  incluindo o fallback `NetIncomeLoss`→`ProfitLoss` da Simon Property) e HGLG11 (resolução real,
  cache confirmado na 2ª chamada). Suite completa **196/196** sem regressão. Fecha a Fase 1.11 —
  desbloqueia o resto da Fase 14.4 do Anchor (`main_us_stock`/`main_reit`/`main_etf_us`,
  benchmarks, `resolve_fii_cnpj`).
- [x] 1.12 — 4 indicadores ETH novos, via CoinMetrics Community API (Sessão 12): o dashboard de
  cripto do Anchor tinha 5 dos 9 indicadores de topo de ciclo do ETH manuais desde as Sessões
  5/6/21 (MVRV Z-Score, Puell Multiple, Exchange Netflow, Staking Yield, Active Addresses Trend)
  por falta de fonte gratuita conhecida na época (só Glassnode/CryptoQuant/Etherscan Pro/
  stakingrewards.com, todos pagos). Pesquisa nova (não só por memória — testada ao vivo contra a
  API real) achou a CoinMetrics Community API (`community-api.coinmetrics.io`, sem chave, sem
  cadastro, ETH com histórico diário completo desde 2015-08-08, ~4048 pontos, 1000 req/10min por
  IP) cobrindo 4 dos 5: `CapMrktCurUSD`+`CapMVRVCur` (MVRV Z-Score, `RealizedCap` derivado —
  `CapRealUSD` cru vem bloqueado no tier grátis, mas a razão pronta não), `IssTotUSD` (Puell
  Multiple), `AdrActCnt` (Active Addresses Trend), `FlowInExUSD`/`FlowOutExUSD` (Exchange
  Netflow). Staking Yield continua sem fonte grátis (beaconcha.in parou de aceitar chamada sem
  chave em 2026, testado ao vivo; CoinMetrics não tem métrica de ETH staked no tier grátis) —
  segue manual. `api/app/sources/cripto_coinmetrics.py` novo (4 funções, mesmo estilo dos outros
  3 clientes cripto) + 4 entradas novas em `crypto_indicator_catalog.py`
  (`mvrv-z-score`/`puell-multiple`/`exchange-netflow`/`active-addresses-trend`) — **nenhum
  router/schema/service/migration novo**, o endpoint genérico `GET /v1/crypto/eth-indicators/
  {indicator_code}` (Sessão 5) já resolvia qualquer código do catálogo. **Achado real ao vivo**:
  `page_size` do tier grátis tem teto de 10000 (não documentado nos resultados de busca
  consultados) — a primeira tentativa com `page_size=20000` (achando que "quanto maior, melhor"
  garantiria pegar a série inteira) quebrou com 400 antes de eu confirmar o teto real via
  request direto. Verificado ao vivo os 4 endpoints novos com valores plausíveis (MVRV Z-Score
  0.15, Puell Multiple 0.98, Exchange Netflow -0.029, Active Addresses Trend -6.3%), cache
  confirmado na 2ª chamada. Suite completa **203/203** sem regressão (+7 testes novos).
- [x] 1.13 — Meta Selic diária + curva DI futuro (PRE), via BCB SGS e B3 "Pesquisa por Pregão"
  (Sessão 14): fecha os 2 itens de brainstorm "Indicadores de juros brasileiros" da Sessão 11
  (ver `ROADMAP.md`). **Selic**: `fetch_daily_series` novo em `bcb_sgs.py` (código 432, Meta
  Selic definida pelo Copom, % a.a.) — endpoint `GET /v1/rates/selic/{series_code}` (catálogo
  próprio, `selic_catalog.py`, separado do `catalog.py` mensal que é explicitamente travado a
  CDI/IPCA). **Achado real ao vivo, não documentado em pesquisa nenhuma consultada antes de
  implementar**: BCB SGS recusa (HTTP 406) uma busca sem `dataInicial` numa série *diária*
  ("O sistema aceita uma janela de consulta de, no máximo, 10 anos") — `fetch_monthly_series`
  nunca bateu nisso por só servir séries mensais. `fetch_daily_series` pagina em janelas de 9
  anos a partir de 1994 (mesmo raciocínio inofensivo do `b3_index_stats.py` pra anos antes da
  base de um índice). **DI futuro**: `b3_taxa_swap.py` novo, porta a lógica de download/parse do
  `pyettj` (referência externa) pro arquivo `TaxaSwap.ex_` do sistema legado "Pesquisa por
  Pregão" da B3 (`www.b3.com.br/pesquisapregao/download?filelist=TS{YYMMDD}.ex_,` — diferente do
  UP2DATA novo, que ficou atrás de Cloudflare em dez/2025), filtrando a curva `PRE` (DIxPRE).
  Endpoint `GET /v1/rates/di-futures-curve/{reference_date}` retorna a curva completa (~270
  vértices). Data sem pregão (fim de semana/feriado) — B3 devolve um zip de 22 bytes, tratado
  como "sem dado" (404), não erro. Os dois models novos (`selic_daily`, `di_futures_curve`,
  migration `0008`) reaproveitam `get_or_refresh_list` (`append_only_list_cache.py`) **sem
  nenhuma modificação** — a curva DI parecia precisar de uma chave de 3 colunas (entidade+data+
  vértice), mas não tem entidade além da própria `reference_date`, que faz o papel de id_column
  enquanto `dias_uteis` faz o de date_column, exatamente como `reference_year` faz pro REIT
  (Fase 1.11.2). Verificado ao vivo: Selic meta com 10.058 pontos desde 1999-03-05 (valor atual
  14,00% a.a.), curva DI de 2026-09-15 com 272 vértices (vértice de 1 dia 13,90% a.a., batendo
  exatamente com a série BCB 1178 do mesmo dia), 2026-09-13 (domingo) e slug Selic desconhecido
  retornando 404 corretamente, cache confirmado na 2ª chamada dos dois. Suite completa
  **225/225** sem regressão (+22 testes novos).

- [x] 1.14 — Câmbio multi-moeda (Sessão 15): fecha o item de brainstorm "Câmbio multi-moeda"
  da Sessão 11 (ver `ROADMAP.md`) — pedido explícito do dono do projeto por cotação entre
  **moedas quaisquer** (ex. USD/EUR), não só pares vs. Real. **Achado que derrubou a hipótese
  original do roadmap** (que presumia precisar de BCB PTAX pra BRL + uma fonte separada pra
  cross entre estrangeiras): o mesmo endpoint não-oficial do Yahoo Finance que
  `acoes_yahoo.py` já usa pra ações/metais aceita qualquer par de moedas via convenção de
  ticker `{BASE}{QUOTE}=X` — confirmado ao vivo `USDBRL=X`, `EURUSD=X`, `EURBRL=X` e, mais
  importante, `GBPJPY=X` (cross entre duas moedas não-BRL, sem nenhuma delas ser a moeda de
  cotação "nativa" de nenhum provider dedicado), além de ordem invertida (`ARSUSD=X`,
  `TRYJPY=X`) e histórico de 10 anos com o mesmo shape que `fetch_price_history` já parseia.
  Ticker desconhecido devolve HTTP 404 real, já absorvido pelo `YahooFinanceError` existente
  via `raise_for_status()`. **Fecha com uma fonte só, sem cliente HTTP novo** — mesmo reuso
  que `metals_catalog.py` já estabelece (`acoes_yahoo.fetch_quote`/`fetch_price_history` com
  `suffix=""`).
  **Design**: diferente de `metals_catalog.py` (mapeamento opaco código→símbolo, ex.
  "xau"→"GC=F", por isso precisa ser um catálogo de *pares* fixo), a conversão par→ticker de
  câmbio é mecânica (`"eurusd"` → `"EURUSD=X"`, só maiúsculas) — catalogar pares fixos
  contrariaria o próprio pedido de "moedas quaisquer". `currency_catalog.py` whitelista
  **moedas individuais** (17 códigos ISO 4217: majors G10-ish, BRL, CNY — maior parceiro
  comercial do Brasil — e Mercosul/LatAm: ARS/UYU/PYG/CLP/COP/PEN/MXN, alinhado ao público-alvo
  do projeto, `CONTEXT.md`), e um par é válido se as duas metades estiverem no catálogo e forem
  diferentes — até 17×16=272 pares sem whitelist especulativa de par. Deliberadamente fora:
  moedas de valor ultra-baixo tipo VND (achado ao vivo: Yahoo arredonda pra `0,0` na própria
  precisão reportada). Validação de catálogo acontece **antes** de qualquer chamada ao Yahoo
  (mesma convenção "sem código especulativo" de metais/B3-index/Selic) — `UnknownCurrencyPairError`
  vira 404 sem tocar a rede. `CurrencyQuote`/`CurrencyPriceHistory` (migration `0009`) não têm
  coluna `name` como `MetalQuote` tem — `base_currency`/`quote_currency` são derivados de
  `pair_code` em tempo de leitura, não persistidos. TTL: reaproveita `stock_quote_ttl_seconds`/
  `cache_ttl_seconds` existentes, mesma decisão que metais já tomou (sem TTL dedicado novo).
  Endpoints `GET /v1/currencies/{pair_code}/quote` e `/price-history`.
  **Verificado ao vivo**: `eurusd` (1,1539/1,1541 USD), `usdbrl` (5,1402 BRL), `gbpjpy` (cross
  entre duas moedas não-BRL, 208,529 JPY), `arsusd`/`copbrl` (pares LatAm), `usdusd` e par com
  componente desconhecido retornando 404 sem chamar o Yahoo, cache confirmado na 2ª chamada,
  histórico de `eurusd` com 2.601 pontos desde 2016-09-15. Suite completa **234/234** sem
  regressão (+9 testes novos). Resta só gestão de opções como item de brainstorm sem fonte
  pesquisada (ver `ROADMAP.md`).

- [x] 1.15 — Gestão de opções: catálogo de séries + cotação EOD (Sessão 16): fecha o item de
  brainstorm "gestão de opções" da Sessão 11 (ver `ROADMAP.md`) para ações e ETF/índice
  (ex: BOVA11), escopo confirmado com o dono do projeto. **Pesquisa de fontes ao vivo**:
  confirmado que não existe fonte grátis para bid/ask, open interest ou gregas/IV (Yahoo Finance
  não tem chain de opções B3 — testado ao vivo, vazio pra PETR4.SA/VALE3.SA/BOVA11.SA; UP2DATA
  segue atrás de Cloudflare desde dez/2025; bolsai não cobre derivativos). Duas fontes B3
  gratuitas resolvem cadastro + preço: **Séries Autorizadas**
  (`b3.com.br/lumis/portal/file/fileDownload.jsp?fileId=...`, arquivo estático pipe-delimited,
  sem chave) dá o universo de séries registradas (ativo-objeto, call/put, strike, vencimento,
  estilo); **COTAHIST** (`bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{yyyy}.ZIP`, mesma
  linhagem legada que `b3_taxa_swap.py` já usa) dá o último preço realmente negociado — 86% das
  ~2,8M linhas do arquivo anual de 2026 são linhas de opção (`TPMERC` 070/080). **Achado real não
  documentado em nenhuma pesquisa prévia**: não existe arquivo diário do COTAHIST
  (`COTAHIST_D{ddmmyy}.ZIP` devolve uma página de erro, não um zip) — só o anual público,
  confirmado ao vivo. **Achado de design que mudou o plano original**: como cada série só
  interessa pelo *último* preço (não histórico), `option_eod_quotes` virou uma tabela de 1 linha
  por série (como `stock_quotes`), não append-only como o plano inicial previa — o parser do
  COTAHIST já teria que escanear o arquivo inteiro de qualquer forma, então guardar só o mais
  recente por série evita inflar a tabela sem necessidade. **Padrão novo no projeto**: as duas
  fontes não buscam por identificador (ao contrário de toda fonte anterior) — é um arquivo só
  pro mercado inteiro, refresh dispara um delete-e-reinsere (série, mesmo raciocínio de
  `FiiProperty`) ou upsert em massa (cotação EOD) global, com frescor rastreado via
  `MAX(fetched_at)` da tabela toda, não por `underlying_symbol` — `options_service.py` não
  reaproveita `single_row_cache`/`append_only_list_cache` por esse motivo. Sem cache em disco
  do zip (diferente de `cvm_dfp.py`): como o refresh já é gated por TTL global (não por
  request), baixar de novo só quando o TTL expira é suficiente. **Achado real durante a
  implementação**: o campo de ativo-objeto do arquivo de Séries Autorizadas nem sempre é a raiz
  do ticker menos o dígito de classe — a Embraer negocia como "EMBR3" mas sua raiz de opção é
  "EMBJ" (confirmado ao vivo) — gap aceito e documentado (`_root_code()` em
  `options_service.py`), mesmo espírito dos achados de CNPJ truncado/fundo renomeado já
  registrados em `PENDING.md`. Também confirmado ao vivo que raiz de opção sempre é prefixo
  exato do ticker de série (zero exceções em ~85 mil linhas testadas) e que um segundo formato
  de linha do mesmo arquivo (tipo "03", opções de índice em pontos, ex. IBOVESPA/SMALL CAP,
  liquidação em R$/ponto) foi deliberadamente deixado fora de escopo — exposição a índice já é
  coberta por opções de BOVA11 (linha tipo "02", mesmo formato de ação). Endpoint único
  `GET /v1/options/{underlying_symbol}/series` devolve todas as séries registradas pro
  ativo-objeto com o último preço EOD quando existe (`last_price: null` pra série registrada mas
  nunca negociada) — ativo-objeto desconhecido devolve `200` com `data: []`, não 404 (mesmo
  raciocínio de `/v1/fiis/{cnpj}/properties`). **Verificado ao vivo**: primeira chamada real
  (`PETR4`) levou ~2min (download+parse do COTAHIST anual, ~80MB comprimidos/700MB
  descomprimidos, ~2,8M linhas — mesma ordem de grandeza dos ~19s que o payout médio 5a da CVM
  já leva hoje), 4.356 séries retornadas, cruzado byte-a-byte contra o COTAHIST decodificado à
  mão (série PETRJ199: strike 17,61, último preço 31,85 em 2026-09-14, batendo exato); segunda
  chamada em 0,46s com `cached: true`; `BOVA11` (índice via ETF) e `VALE3` retornando séries
  reais; ativo-objeto inexistente (`XYZW9`) retornando `data: []` sem erro; nenhum cache em
  disco criado (confirmado dentro do container). Suite completa **249/249** sem regressão
  (+15 testes novos). **Fora de escopo, fica pra Fase 1.16 futura**: gregas (delta/gamma/theta/
  vega) e volatilidade implícita — exigem um módulo de precificação Black-Scholes novo,
  estimativa de volatilidade e interpolação da curva DI futuro (`rates_service.py`, Fase 1.13)
  no vértice certo; nenhuma fonte grátis fornece isso pronto.

- [x] 1.16 — Gregas de opções via Black-Scholes (Sessão 16, mesmo dia): fecha o item que a 1.15
  deixou pra depois. **Sem tabela/migration nova** — gregas são uma view computada sobre 4
  fontes já cacheadas de forma independente (série+cotação EOD da opção, Fase 1.15; cotação do
  ativo-objeto, `stock_service.py`; curva DI futuro, Fase 1.13), recomputada a cada chamada
  (cachear o resultado não faria sentido — muda a cada tick do preço do ativo-objeto).
  **Decisão confirmada com o dono do projeto**: o preço do ativo-objeto é informado pelo
  chamador via `underlying_ticker` (query param), não adivinhado pela API — a raiz de opção da
  Fase 1.15 não é suficiente pra saber a classe certa da ação (ON/PN/PNA/...) com segurança
  (Embraer já provou que adivinhar quebra, `PENDING.md` P2), e uma grega calculada com o preço
  do papel errado seria um erro silencioso pior que pedir o ticker de volta pra quem já gerencia
  a posição. `api/app/services/black_scholes.py` novo: matemática pura (stdlib `math`, sem
  numpy/scipy — projeto não tinha essa dependência e uma fórmula fechada não justifica
  introduzir uma), preço/gregas/IV (Newton-Raphson com fallback pra bisseção), fórmulas
  validadas contra o caso de referência de livro-texto (Hull: S=K=100,T=1,r=5%,σ=20% →
  call≈10,4506/put≈5,5735/delta≈0,6368/gamma≈0,018762/vega≈0,3752/theta≈-0,017573/dia).
  Estilo americano (`option_series.style`) não é distinguido — só aproximação europeia, sem
  fonte grátis pra validar prêmio de exercício antecipado, documentado como simplificação
  consciente. `api/app/services/option_greeks_service.py` novo orquestra: reaproveita os
  refreshes globais da Fase 1.15 (tornados públicos:
  `refresh_series_catalog_if_stale`/`refresh_eod_quotes_if_stale` em `options_service.py`),
  busca a série+último preço, cotação do ativo-objeto (`stock_service.get_or_refresh_quote`,
  TTL de 300s já existente), curva DI futuro (`rates_service.get_or_refresh_di_futures_curve`,
  recuando dia a dia até 10 dias em fim de semana/feriado, mesmo padrão já usado pela curva em
  si) interpolada linearmente por `dias_corridos` no prazo até o vencimento (eixo em dias
  corridos, não dias úteis — evita implementar um calendário de feriados só pra isso; `T` da
  opção usa a mesma base). IV resolvida a partir do **último preço realmente negociado** (que
  pode ser de dias/semanas atrás pra série pouco líquida) — a resposta expõe `last_trade_date`
  explicitamente em vez de esconder a proveniência, mesmo espírito de não fazer julgamento de
  negócio que não é da API (ex: Fear&Greed cru sem classificação, Fase 1.5). Endpoint
  `GET /v1/options/{series_ticker}/greeks?underlying_ticker=...` — pequeno refactor do router
  (prefixo de `/v1/options/{underlying_symbol}` fixo pra `/v1/options` puro com duas rotas, URL
  de `/series` da 1.15 inalterada). Erros mapeados: 404 série desconhecida/nunca negociada, 422
  opção vencida ou preço abaixo do valor intrínseco (nenhuma vol positiva reproduz — sinal de
  preço obsoleto, não bug), 502 qualquer fonte fora do ar. **Verificado ao vivo**: fórmulas
  conferidas por script solto antes de implementar; `GET /v1/options/PETRL522/greeks?
  underlying_ticker=PETR4` (call dez/2026, strike 49,91, spot 49,06, quase-no-dinheiro) devolveu
  delta 0,576, gamma 0,034, theta -0,033/dia, vega 0,097, IV implícita 46,49% (faixa plausível
  pra Petrobras), taxa livre de risco 13,59% interpolada da curva DI de 2026-09-15 (curva de
  hoje ainda não publicada no momento do teste, fallback pro dia anterior funcionou); série
  desconhecida e série sem negociação (`PETRU696`) retornando 404; segunda chamada em 0,25s
  (tudo em cache). Suite completa **266/266** sem regressão (+17 testes novos, incluindo
  round-trip de IV: gera um preço BS com uma vol conhecida e confirma que o solver reconstrói a
  mesma vol). Fecha o último item de brainstorm que tinha pesquisa de fonte concluída — restam
  só as 3 ideias mais antigas do roadmap nunca sequenciadas (Open Finance, Unified Payment API,
  SDK do catálogo de fontes, ver `ROADMAP.md`), sem pesquisa de fonte feita ainda.

### Fase 2 — Engine Fiscal (SEFAZ)

Do blueprint original — NF-e/NFS-e via certificado digital A1, validação de schemas XML,
geração automática de DANFE. Sem desenho ainda; ver `ROADMAP.md`.

### Fase 3 — Meta Cloud API & Automação (WhatsApp)

Do blueprint original — WhatsApp Business API oficial (Meta Cloud API), disparo automático
pós-pagamento, abstração de tokens/webhooks/Message Templates. Sem desenho ainda.

### Fase 4 — Workspace Web App

Do blueprint original — painel gerenciado pro empreendedor não-técnico, modelo
pay-as-you-go, hub de comunicação (e-mail/WhatsApp), DRE simplificado, motor de automação
("Se X, então Y e Z"). Sem desenho ainda.
