## Roadmap de Evoluções Planejadas

### Visão completa do blueprint original (registrado na Sessão 1)

O blueprint (`blueprint_plataforma_opensource.md.docx`, lido e removido do repo na Sessão 1)
descrevia 3 camadas: (A) Ponte para Desenvolvedores (APIs & SDKs — pagamentos unificados,
fiscal, WhatsApp, finanças/Open Finance), (B) Workspace do Empreendedor (web app), (C) Módulo
B3 & Mercado Financeiro. A decisão desta sessão foi começar pela fatia financeira de (A) e (C)
combinadas — a Finance API — por já ter um consumidor real pronto (o Anchor) e por ser a base de
que as outras camadas dependem (ex: o DRE do Workspace precisa de dados financeiros
centralizados; a conciliação de caixa corporativo do módulo B3 também).

### Modelo Open-Core & Monetização (do blueprint original)

| Componente | Versão Open-Source (Community) | Versão Cloud Hospedada (SaaS) |
|---|---|---|
| Público-Alvo | Desenvolvedores, Engenheiros de Software, DevOps | Empreendedores, Startups, Pequenos Lojistas |
| Hospedagem | Infraestrutura própria (VPS, Docker, PostgreSQL) | Nuvem nativa gerenciada (Zero setup) |
| Custo de Infra | Pago pelo próprio dev | Incluído na bilhetagem por uso |
| Modelo financeiro | Gratuito / Licença permissiva (MIT/AGPL) | Pay-as-you-go (margem sobre micro-transações) |

Monetização por consumo, exemplos do blueprint original: R$ 0,15 por nota fiscal emitida
(Fase 2), repasse do custo Meta + margem por mensagem enviada (Fase 3), micro-taxa sobre
webhooks e baixa automática de boletos/Pix. Nenhum desses se aplica à Fase 1 (dados
financeiros) ainda — como cobrar pelo uso da Finance API (por chamada? por volume de dado? tier
gratuito generoso pro open-source, cobrança só na versão cloud?) fica em aberto até a API
existir.

### Migração do Anchor pra Finance API — ideia central desta sessão (Sessão 1)

O Anchor (`../../anchor`) tinha `data-collector/` — 12 clientes Python independentes (ver
catálogo completo em `CONTEXT.md`), cada um escrevendo direto no SQLite local do app, disparado
como subprocess sob demanda pelo botão da UI. Isso funcionava, mas: (1) não tinha cache/reuso
entre os apps do Anchor (desktop, mobile ainda não sincroniza, futuro cross-device via TruthID);
(2) qualquer outro projeto financeiro do mesmo autor reimplementaria tudo de novo; (3) sem
camada de confiabilidade compartilhada (retry, fallback, normalização) além do que cada script
fazia sozinho. **Migrado na Sessão 7 (Fase 1.7, ver `PHASE.md`)** — híbrido, não 100%: o que a
Finance API cobre virou HTTP; o resto (ver "Fase 1.6b" abaixo) continua local.

### Fase 1.6b → agora Fase 1.11 — fechar a lacuna deixada pela migração híbrida (completa, ver `PHASE.md`)

A 1.7 (Sessão 7) revelou que a Finance API não cobre tudo que o Anchor precisa — 4 capacidades
continuavam rodando local no `data-collector/` dele por falta de endpoint equivalente:
- Cotação/técnicos/dividendos/histórico de preço pra ticker **sem sufixo `.SA`** (ação
  americana comum, ETF US, REIT) — `/v1/stocks/...` só servia B3. **Fechado (1.11.1)**: 5
  endpoints novos sob `/v1/us-stocks/{ticker}/quote,technicals,dividends-avg,price-history,
  dividend-payments`.
- Indicadores imobiliários de REIT (FFO/AFFO não existem como tag XBRL, mas receita/patrimônio/
  LPA/lucro dão pra automatizar, mesmo espírito de `/v1/companies/...`). **Fechado (1.11.2)**:
  `GET /v1/us-stocks/{ticker}/reit-fundamentals`.
- IBOV (`^BVSP`) — mesmo problema do primeiro item, é Yahoo sem sufixo. **Fechado**: passa
  pelos mesmos endpoints do 1.11.1, sem endpoint próprio.
- Resolução ticker→CNPJ de FII (`resolve_cnpj`) — cruza bolsai + nome oficial da CVM, nunca
  desenhada como endpoint (decisão da Sessão 4 do Anchor). **Fechado (1.11.3)**:
  `GET /v1/fiis/resolve/{ticker}`.

**Sessão 10**: pedido explícito do dono do projeto pra fechar de vez o ciclo Open-Core (ver
"Monetização" abaixo) do lado do Anchor — apagar `data-collector/` de vez, rodando a versão
free/self-hosted da Finance API localmente "já instalada" (sem Docker/Postgres pro usuário
final) e deixando um espaço de configuração pra apontar pra uma futura instância Cloud paga.
Isso virou um plano cross-repo em 2 fases do lado Lume — **1.10** (modo sidecar
SQLite/binário compilado, concluída na Sessão 10, ver `PHASE.md`) e **1.11** (as 4 capacidades
acima, **concluída — ver `PHASE.md`**) — mais 5 sub-fases do lado Anchor (Fase 14 do `PHASE.md`
dele: CI/bundling do sidecar, lifecycle+client em Rust, Settings Local/Remote, porta do
fetch+write Python→Rust, limpeza final do `data-collector/`). A 1.11 era pré-requisito pra
Anchor conseguir apagar `data-collector/` por completo (Fase 14.4/14.5 dele só fecham depois que
nada mais depender de lógica local) — com a 1.11 fechada, os 3 fluxos que restavam bloqueados na
Fase 14.4 do Anchor (`main_us_stock`/`main_reit`/`main_etf_us`, benchmarks, `resolve_fii_cnpj`)
ficam livres pra portar.

### Ingestão proativa por agendamento — Finance DB desacoplado do request (Brainstorm — sem `/plan`)

**Contexto**: hoje todo domínio (`macro_series_service.py`, `stock_service.py`, etc.) segue o
mesmo padrão cache-through **100% reativo** — o Postgres só é alimentado quando um consumidor
faz uma requisição e o `fetched_at` daquele identificador já estourou o TTL (`freshness.py`).
Isso é exatamente a linha ainda em aberto na tabela de decisões do `ARCHITECTURE.md`
("Cadência de coleta por fonte"). Funciona bem pro estágio atual (Anchor como único consumidor),
mas tem duas consequências que só ficam visíveis em produção com tráfego real: (1) quem faz a
requisição que estoura o TTL paga o custo da fonte externa na hora — às vezes minutos (o
COTAHIST anual da Fase 1.15 leva ~2min na primeira chamada); (2) o Postgres nunca é "nosso banco
de verdade" de forma independente — ele é só um cache com validade, que desaparece de fato (fica
stale) se ninguém pedir aquele dado por tempo suficiente.

**Proposta**: separar duas responsabilidades hoje fundidas no mesmo service — **ingestão**
(busca na fonte externa + upsert no Postgres, em cadência própria por tipo de dado, sem nenhum
request de consumidor envolvido) e **serving** (a API só lê do Postgres; no caminho feliz, nunca
fala com uma fonte externa dentro do ciclo de um request). As funções de fetch+upsert que já
existem em cada `*_service.py` são exatamente o que um job de ingestão executaria — não é código
novo por fonte, é a mesma lógica disparada por um agendador em vez de por um handler HTTP.

- **Cadência por tipo de dado** (reaproveitando o TTL que cada fonte já declara hoje como pista):
  intraday pra cotação (stock/crypto/currency quotes, ~1-5min, mesmo valor de
  `stock_quote_ttl_seconds`); diária pra fonte que fecha 1x/dia (EOD/COTAHIST de opções, curva
  DI, Selic diária, índices B3 — rodar logo após o fechamento do pregão); baixa frequência pra
  fundamento (CVM/SEC/bolsai, macro mensal do BCB — 1x/dia já é folgado dado TTL de 24h+ que já
  existe).
- **Componente novo**: um worker/scheduler separado do processo da API (serviço novo no
  `docker-compose.yml`, ao lado de `api`/`docs`) — não dentro do próprio FastAPI, pra não competir
  pelo threadpool com requests reais de consumidor. Dado o padrão self-host já estabelecido (sem
  infra gerenciada), a opção mais simples é um processo Python com **APScheduler** rodando as
  mesmas funções de `sources/`+upsert (mesma stack, sem componente novo de infra) — alternativa
  mais pesada seria Celery beat+worker, que traz retry/concorrência distribuída mais robustos mas
  exige broker novo (Redis), provavelmente desproporcional ao volume de fontes atual (~15
  domínios).
- **Cache-through não é descartado — vira rede de segurança**: um identificador nunca antes
  buscado (ex: ticker novo que ninguém pediu ainda) continua disparando fetch síncrono na
  primeira chamada, como hoje. Depois disso, o job de ingestão assume a atualização periódica e o
  request handler nunca mais precisa falar com a fonte externa pra esse identificador. Modelo
  híbrido, não uma reescrita all-or-nothing dos services existentes.
- **Observabilidade nova, necessária**: hoje uma falha de fonte aparece como erro (ou stale) na
  resposta de um request real — um job rodando sozinho de madrugada não tem esse sinal. Precisa
  de um registro de execução por fonte (tabela nova, ex. `ingestion_runs`: fonte, iniciado_em,
  terminado_em, status, linhas afetadas, erro) pra saber que uma fonte parou de responder sem
  esperar um consumidor reclamar.
- **Idempotência já resolvida**: todo upsert existente (`ON CONFLICT DO UPDATE`/`DO NOTHING`) já
  é seguro de rodar em cadência fixa sem duplicar nem corromper dado — nenhuma mudança necessária
  nessa camada, só quem chama muda (scheduler em vez de request).
- **Quando faz sentido sequenciar**: quando o projeto sair do estágio MVP/self-host de
  único-consumidor (Anchor) pra ter tráfego real de múltiplos consumidores simultâneos — hoje a
  complexidade operacional de manter um scheduler (monitorar falha silenciosa, cadência por
  fonte, etc.) não se paga ainda. Registrado aqui como proposta de arquitetura pra quando essa
  fase chegar; não sequenciado em nenhuma Fase do `PHASE.md` ainda, nem passou por `/plan`.

### Reposicionamento do Lume — escopo, modelo local vs. hospedado, `DataProvider` plugável (Brainstorm — sem `/plan`, Sessão 18)

> Origem: notas soltas do dono do projeto (`lume.md` na raiz, incorporado aqui e removido do
> repo na Sessão 18). **São ideias pra debater e possivelmente implementar — nada aqui foi
> decidido em definitivo nem passou por `/plan`.** Onde a ideia conflita com o que já está
> documentado/implementado, o conflito está anotado explicitamente em vez de resolvido.

**Renomeação**: a nota ainda fala "EasyBusiness Finance API foi renomeada para Lume (mudança
ainda não aplicada no repositório)" — isso já está desatualizado: o repo já é `masterlxz/lume` e a
documentação já usa o nome Lume. Resta só o histórico (`SESSIONS.md` das primeiras sessões cita
`easybusiness`), que fica como está por ser log.

#### 1. Escopo: "centro de informações", não plataforma de integrações

- Lume passa a ser definido como um **centro de informações** — hoje financeiras, mas sem se
  restringir a finanças no futuro (outros domínios de dado podem entrar).
- **Integrações burocráticas (NF-e, boleto, B3) saem do Lume** — viraram um projeto open-source
  separado, hoje parado (referenciado como `integracoes-br.md`, arquivo que não está neste repo).
  O `b3-sdk` desse projeto separado pode, no futuro, **alimentar** o Lume com dado de custódia —
  mas o código de integração fica lá, o Lume só consome.
- **Conflito com a documentação atual (a debater)**: `OVERVIEW.md` ("plataforma open-source de
  automação, finanças e gestão para o empreendedor brasileiro"), `CONTEXT.md` (Vision, Non Goals)
  e `PHASE.md`/`OVERVIEW.md` (Fase 2 — Engine Fiscal SEFAZ, Fase 3 — WhatsApp/Meta, Fase 4 —
  Workspace) ainda descrevem a visão de 3 camadas do blueprint. Se o reposicionamento for
  confirmado:
  - Fase 2 (SEFAZ/NF-e) sai do Lume de vez → projeto de integrações.
  - "Unified Payment API" e baixa de boleto/Pix (Ideias de Expansão abaixo, e exemplos de
    monetização do blueprint — R$ 0,15/nota, micro-taxa sobre boleto/Pix) também saem.
  - Fase 3 (WhatsApp) e Fase 4 (Workspace) ficam sem dono claro — não são "informação" nem
    "integração burocrática". Precisa decidir se morrem, viram consumidores do Lume (como o
    Anchor) ou vão pra outro projeto.
  - A nota não fala de B3 de mercado (cotação, COTAHIST, opções, curva DI) — assumido que isso
    **continua** no Lume, por ser dado/informação; o que sai é a integração operacional
    (custódia, CEI/área do investidor). Confirmar.
  - Open Finance (extratos bancários) fica na fronteira: é dado, mas exige integração
    regulada/consentimento — decidir de que lado cai.

#### 2. Modelo local (grátis) vs. hospedado (pago)

- **Restrição de custo**: a versão gratuita/local **não pode gerar custo pro Fabio**.
- Lume roda **localmente na máquina do usuário por padrão** (grátis). Uma versão **hospedada
  pelo Fabio seria paga** — mesmo padrão de tier gerenciado já usado no TruthID. Isso responde
  parcialmente a pergunta em aberto de "Modelo Open-Core & Monetização" acima ("como cobrar pelo
  uso da Finance API"): o que se cobra é a hospedagem/conveniência (e dado premium, ver item 3),
  não o uso local.
- Já é coerente com o que existe: Fase 1.10 (modo sidecar SQLite, binário PyInstaller) é
  exatamente o "Lume local grátis".
- **Ideia nova — instância local compartilhada**: Anchor continua empacotando o binário do Lume
  como sidecar, mas com **fallback**: na inicialização checa se já existe uma instância de Lume
  rodando localmente (em porta/socket fixo); se existe, usa essa instância compartilhada; se não,
  sobe a própria cópia embutida.
- Motivação: se o **Warden** (outro projeto do ecossistema — primeiro registro dele neste repo)
  também estiver rodando na máquina, Anchor e Warden **compartilham a mesma instância de Lume
  automaticamente**, sem o usuário instalar nada extra — e, por consequência, compartilham cache
  (menos chamadas às fontes externas, menos risco de rate limit).
- **Pontos a debater antes de qualquer `/plan`**:
  - Conflito direto com o design atual do sidecar: `api/sidecar_main.py` deliberadamente usa
    porta atribuída pelo SO (ou `PORT` do env) e anuncia via stdout `SIDECAR_PORT=<port>`,
    justamente pra **não** chutar porta fixa que pode colidir. Descoberta por porta fixa reabre
    isso — alternativas: socket Unix/named pipe em caminho conhecido, ou um arquivo de
    descoberta (lockfile em diretório de dados do usuário com porta+PID+versão).
  - Identificação: bater numa porta e achar "algo" não prova que é um Lume — precisa de um
    endpoint de handshake (ex: `/health` com nome+versão da API) antes de confiar.
  - Ciclo de vida: se o Anchor subiu a instância e o Warden passou a usá-la, o que acontece
    quando o Anchor fecha? Opções: instância vira daemon independente (o "Lume-daemon" citado
    na nota), refcount de clientes, ou quem subiu mata e o outro sobe a própria (perdendo o
    compartilhamento).
  - Versão: Anchor e Warden podem embutir versões diferentes do Lume. Precisa de regra de
    compatibilidade (ex: usar a compartilhada só se a versão da API for ≥ a mínima que o cliente
    exige; senão sobe a própria).
  - Onde fica o SQLite local compartilhado (diretório de dados comum do "ecossistema", não o do
    Anchor) e autenticação local (`X-API-Key` hoje é por env — dois apps precisam conhecer a
    mesma chave, ou o modo local aceita só loopback sem chave).

#### 3. Dado premium sem quebrar o "Anchor grátis/self-hosted"

- **Preocupação**: comprar dado de melhor qualidade no futuro não pode quebrar a promessa de
  Anchor grátis/self-hosted.
- **Solução proposta**: interface `DataProvider` com múltiplas implementações plugáveis:
  - **Fonte grátis por padrão** — o que já existe hoje (`api/app/sources/`).
  - **BYO-key** — usuário cola a própria chave de um provedor pago; ele paga a assinatura dele,
    sem custo pro Fabio.
  - **Dado premium reservado ao tier hospedado** — aí o Fabio absorve o custo, porque está
    cobrando por isso.
- **Princípio proposto pro ecossistema inteiro** (não só Lume): **grátis + self-hosted sempre
  funciona com qualidade padrão; pago é conveniência ou qualidade extra, nunca funcionalidade
  básica trancada.** Já é o padrão no TruthID (Ledger grátis vs. facilitado pago) e no
  Lume-daemon (local grátis vs. hospedado pago). Se aceito, vale registrar também nos
  `GUIDELINES.md`/docs dos outros projetos.

#### 4. Esboço da interface `DataProvider` (não implementado)

A nota usa vocabulário de Rust ("traits"); o Lume é Python — o equivalente seria
`typing.Protocol` (ou ABC) por categoria.

- **Interfaces separadas por categoria de dado** (ex: `QuoteProvider`, `FundamentalsProvider`,
  `CryptoScoreProvider`) em vez de uma única — nem todo provider cobre todas as categorias.
- **`ProviderRegistry`** resolve qual provider usar por chamada, em **cascata de prioridade**:
  BYO-key primeiro se configurada; cai pra grátis se falhar ou não estiver configurada.
- **Chave do usuário no keyring do SO**, nunca em texto puro em arquivo de config ou banco.
- **Cache como camada ortogonal aos providers** (TTL por tipo de dado — cotação expira em
  segundos, fundamentos em dias), não reimplementado dentro de cada provider. É o que permite
  Anchor e Warden compartilharem cache quando batem na mesma instância local.
- **Contrato de erro distingue "sem dado" de "provider caiu"** — pra quem consome decidir se
  tenta o próximo provider da cascata ou mostra erro pro usuário.

**Como isso se encaixa no código atual (notas pra debate)**:
- Hoje cada `*_service.py` chama **diretamente** um módulo específico de `sources/` e faz
  fetch+upsert+freshness no mesmo lugar. A camada de cache já é *quase* ortogonal
  (`freshness.py`, `single_row_cache.py`, `append_only_list_cache.py`), mas a escolha da fonte
  está fixa no service. O refactor seria: service pede à categoria via registry, registry
  escolhe o provider, cache fica em volta.
- Já existem casos de "cascata" hard-coded que viram candidatos naturais: bolsai vs. Yahoo pra
  ações B3, CoinGecko/CoinMetrics/DefiLlama em cripto.
- O contrato de erro já é parcialmente assim, mas inconsistente: há erros de "sem dado"
  (`NoDividendDataError`, `TickerNotFoundError`, `FundNotFoundError`, … — subclasses de
  `ValueError`) e de "fonte falhou" (`YahooFinanceError`, `B3TaxaSwapError`,
  `RiskFreeRateUnavailableError` — `RuntimeError`), cada um definido localmente por service. A
  proposta pediria uma hierarquia comum (ex: `NoDataError` vs. `ProviderUnavailableError`).
  `PENDING.md` P1 (FII desconhecido vs. FII sem imóvel) é o mesmo tipo de problema.
- **Proveniência no cache**: se mais de um provider pode preencher a mesma linha, a tabela
  precisa registrar qual provider gerou o dado (e talvez preferir sobrescrever dado grátis
  quando o premium responde, mas não o contrário). A resposta da API poderia expor isso, no
  mesmo espírito de `last_trade_date` das gregas.
- **Keyring vs. servidor**: keyring do SO faz sentido no modo local/sidecar (máquina do
  usuário, lib `keyring` no Python). No modo Docker/self-host de servidor e no hospedado não há
  keyring de usuário — lá a chave viria de env/secret manager. Definir onde BYO-key é suportado
  (provavelmente só no local).
- **Relação com a ingestão proativa** (seção anterior): um scheduler de ingestão precisaria
  decidir com qual provider ingerir — BYO-key do usuário no modo local faz sentido; no hospedado,
  o premium.

### Ideias de Expansão (Brainstorm — sem `/plan`)

- Open Finance de verdade (extratos bancários via Open Finance Brasil) — mencionado no
  blueprint original, não pesquisado ainda.
- Unified Payment API (Asaas, Mercado Pago, Pagar.me, Stripe) — camada (A) do blueprint, ainda
  não sequenciada em relação às Fases 2-4 de `PHASE.md`.
- Expor o catálogo de fontes como um SDK (Python/Node), mesmo padrão que TruthID e Anchor usam
  pros próprios integradores.
- ~~**Câmbio multi-moeda**~~ — **concluído na Fase 1.14, Sessão 15** (ver `PHASE.md`/
  `ARCHITECTURE.md`). A hipótese de precisar de duas fontes (BCB PTAX + algo à parte pra cross
  entre estrangeiras) não se confirmou: o mesmo Yahoo Finance que `acoes_yahoo.py` já usa cobre
  qualquer par via ticker `{BASE}{QUOTE}=X`, validado ao vivo inclusive pra cross entre duas
  moedas não-BRL (`GBPJPY=X`) — uma fonte só, sem cliente HTTP novo.
- ~~**Indicadores de juros brasileiros — Selic e DI futuro**~~ — **concluído na Fase 1.13,
  Sessão 14** (ver `PHASE.md`/`ARCHITECTURE.md`). Selic saiu do BCB SGS como esperado (código
  432, Meta Selic); DI futuro achou fonte gratuita real (B3 "Pesquisa por Pregão", curva PRE) —
  não precisou de fonte paga nem scraping.
- ~~**Gestão de opções — catálogo + cotação EOD**~~ — **concluído na Fase 1.15, Sessão 16** (ver
  `PHASE.md`/`ARCHITECTURE.md`). Escopo confirmado com o dono do projeto: ações e ETF/índice
  (BOVA11) juntos. Duas fontes B3 gratuitas (Séries Autorizadas + COTAHIST) cobrem cadastro de
  séries e último preço negociado — confirmado que não existe fonte grátis pra bid/ask, open
  interest ou gregas/IV.
- ~~**Gestão de opções — gregas**~~ — **concluído na Fase 1.16, Sessão 16** (ver `PHASE.md`/
  `ARCHITECTURE.md`). Black-Scholes puro (stdlib `math`, sem nova dependência), preço do
  ativo-objeto informado pelo chamador (`underlying_ticker`) em vez de adivinhado — decisão
  confirmada com o dono do projeto pra evitar grega errada por classe de ação errada.
- Objetivo comum dos itens acima: o Anchor precisa ter acesso a tudo isso via Finance API,
  no mesmo modelo já estabelecido (endpoint novo por capacidade, cache-through via Postgres,
  consumido pelo cliente HTTP do Anchor). Dono do projeto não tem certeza de quais fontes usar
  pros itens restantes — pesquisa de fontes é o primeiro passo antes de qualquer `/plan`.
