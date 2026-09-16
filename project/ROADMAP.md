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

### Ideias de Expansão (Brainstorm — sem `/plan`)

- Open Finance de verdade (extratos bancários via Open Finance Brasil) — mencionado no
  blueprint original, não pesquisado ainda.
- Unified Payment API (Asaas, Mercado Pago, Pagar.me, Stripe) — camada (A) do blueprint, ainda
  não sequenciada em relação às Fases 2-4 de `PHASE.md`.
- Expor o catálogo de fontes como um SDK (Python/Node), mesmo padrão que TruthID e Anchor usam
  pros próprios integradores.
- **Câmbio multi-moeda** (pedido do dono do projeto, Sessão 11) — hoje as fontes cambiais
  existentes (se houver) presumivelmente só cobrem par vs. Real; a ideia é suportar cotação
  entre moedas quaisquer (ex. USD/EUR, não só USD/BRL, EUR/BRL). Não pesquisado ainda: fonte de
  dados (BCB PTAX cobre bem vs. BRL, mas cross-rate entre estrangeiras provavelmente precisa de
  outra fonte tipo Yahoo Finance ou um provider de FX dedicado).
- ~~**Indicadores de juros brasileiros — Selic e DI futuro**~~ — **concluído na Fase 1.13,
  Sessão 14** (ver `PHASE.md`/`ARCHITECTURE.md`). Selic saiu do BCB SGS como esperado (código
  432, Meta Selic); DI futuro achou fonte gratuita real (B3 "Pesquisa por Pregão", curva PRE) —
  não precisou de fonte paga nem scraping.
- **Gestão de opções** (pedido do dono do projeto, Sessão 11) — dono do projeto quer que o
  Anchor tenha suporte a gestão de opções (provavelmente opções de ações/índices B3, mas não
  confirmado). Não pesquisado: fonte de dados de opções (cotação, gregas, séries/strikes
  disponíveis) nem se a B3/CVM expõe isso de forma aberta ou se precisa de fonte paga.
- Objetivo comum dos itens acima: o Anchor precisa ter acesso a tudo isso via Finance API,
  no mesmo modelo já estabelecido (endpoint novo por capacidade, cache-through via Postgres,
  consumido pelo cliente HTTP do Anchor). Dono do projeto não tem certeza de quais fontes usar
  pros itens restantes — pesquisa de fontes é o primeiro passo antes de qualquer `/plan`.
