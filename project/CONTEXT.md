# Lume - PRD v0.1 (MVP: Finance API)

## Origem

Este PRD nasce do blueprint original do projeto, `blueprint_plataforma_opensource.md.docx`
(lido na Sessão 1, removido do repo depois de incorporado aqui — ver `SESSIONS.md`). O
blueprint descrevia uma plataforma completa (pagamentos, fiscal, WhatsApp, workspace, B3) —
este documento recorta a fatia que vira MVP: a camada de dados financeiros.

## Vision

Democratizar o acesso a dados financeiros confiáveis (mercado brasileiro e internacional,
cripto, macroeconomia) para desenvolvedores e pequenos empreendedores brasileiros, via uma API
única, simples e open-source — substituindo a necessidade de cada projeto integrar, sozinho,
dezenas de APIs de terceiros diferentes (cada uma com seu formato, limite de taxa, autenticação
e instabilidade).

## Core Problem

Hoje, projetos financeiros pessoais (como o [Anchor](../../anchor)) resolvem coleta de dados
de forma isolada: cada fonte vira um cliente Python próprio, sem cache compartilhado, sem
reuso entre projetos, sem camada de confiabilidade (retry, fallback, normalização de formato)
além do que cada script implementa por conta própria. Todo novo projeto financeiro (pessoal ou
de terceiros) reinventa essa integração do zero.

Além disso, o empreendedor brasileiro sofre com alto custo de SaaS e burocracia (gestão fiscal,
boletos, WhatsApp) — dor que o blueprint completo ataca, mas que tem como pré-requisito uma
camada financeira central confiável (ver `ROADMAP.md` para as fases seguintes do blueprint).

## Core Concepts

- **Finance API**: API HTTP/JSON única, com autenticação por chave, que expõe dados financeiros
  normalizados independente da fonte original.
- **Finance DB**: banco de dados central (candidato: Postgres — ver decisão em `ARCHITECTURE.md`)
  que armazena/cacheia o resultado das coletas, servindo de fonte única de verdade para quem
  consome a API. Cada fonte de dado (catálogo abaixo) alimenta o Finance DB via um job de
  coleta — o equivalente centralizado ao `data-collector/` do Anchor.
- **Consumidor**: qualquer app que troque scripts de coleta próprios por chamadas HTTP. O
  primeiro consumidor-alvo é o próprio Anchor (`desktop/src-tauri`, que hoje chama
  `data-collector/main.py` como subprocess local — vira uma chamada HTTP pra Finance API).

## Catálogo de Fontes de Dados (herdado do Anchor — ponto de partida da Fase 1)

Levantado a partir de `anchor/data-collector/sources/` (Sessão 1). Cada uma vira, na Fase 1,
um cliente dentro da Finance API em vez de um script Python isolado:

| Fonte | Domínio | O que fornece | Observação |
|---|---|---|---|
| Yahoo Finance (`acoes_yahoo.py`) | Ações BR/globais | Cotação atual + histórico | API não-oficial |
| bolsai (`acoes_bolsai.py`) | Ações BR | Fundamentos | Exige API key própria (`BOLSAI_API_KEY`) |
| B3 (`b3_index_stats.py`) | Índices B3 | Estatísticas internas de índices | API interna da B3 |
| Banco Central — SGS (`bcb_sgs.py`) | Macro BR | Séries temporais (Selic, IPCA, câmbio etc.) | Sistema Gerenciador de Séries Temporais |
| CVM Dados Abertos (`cvm_dfp.py`) | Fundamentos BR | Demonstrações financeiras (DFP), base pra DCF/FCFF | Dados abertos governamentais |
| CVM Dados Abertos — FII (`cvm_fii.py`) | Fundos Imobiliários | Dados específicos de FII | Fatia separada do DFP |
| SEC EDGAR (`sec_edgar.py`) | Fundamentos EUA | Equivalente americano da CVM, pra DCF/FCFF | Dados abertos governamentais (EUA) |
| Yahoo Finance — Metais (`metais_yahoo.py`) | Metais preciosos | Cotação de metais | Mesmo provedor do primeiro item |
| CoinGecko (`cripto_coingecko.py`) | Cripto | Preço, market cap, volume | |
| DefiLlama (`cripto_defillama.py`) | DeFi | TVL de chains/protocolos | Série diária |
| alternative.me (`cripto_feargreed.py`) | Cripto | Crypto Fear & Greed Index | |
| ultrasound.money (`cripto_ultrasound.py`) | Ethereum | Supply/net issuance do ETH | |
| CoinMetrics Community API (`cripto_coinmetrics.py`) | Ethereum | Market cap, MVRV, endereços ativos, emissão, fluxo de exchange | Sem chave, histórico completo desde 2015 — primeira fonte deste catálogo que **não** veio herdada do Anchor (Sessão 12, ver `PHASE.md`) |

**Não migrado ainda / fora do catálogo**: o `data-collector/` original do Anchor foi apagado por
completo na Fase 14.5 dele (Sessão 92) — o catálogo acima já cobre tudo que ele fazia. Fontes
novas que o Anchor venha a precisar de agora em diante entram direto aqui, não lá.

## Fluxo de Dados (visão MVP)

```text
[Fontes externas: Yahoo, bolsai, B3, BCB, CVM, SEC EDGAR, CoinGecko, DefiLlama, ...]
           │  (jobs de coleta, agendados ou sob demanda)
           ▼
[Finance DB — dado normalizado e cacheado]
           │
           ▼
[Finance API — HTTP/JSON, autenticação por chave]
           │
           ▼
[Consumidores: Anchor (primeiro), outros projetos, usuários externos (pay-as-you-go futuro)]
```

## Non Goals (MVP / Fase 1)

- Módulo fiscal (SEFAZ/NF-e) — Fase 2 do blueprint, não desta fase.
- WhatsApp/Meta Cloud API — Fase 3 do blueprint.
- Workspace web app pro empreendedor não-técnico — Fase 4 do blueprint.
- Gateway de pagamentos unificado (Pix/boleto/Stripe) — mencionado no blueprint original mas
  fora do escopo financeiro-de-dados desta Fase 1; decidir depois se entra como extensão da
  Finance API ou como módulo separado.
- Migrar o código do Anchor "como está" — a ideia é reimplementar os clientes de fonte de dado
  de forma centralizada, não copiar os arquivos Python 1:1 (ver `GUIDELINES.md`).

## Monetization (do blueprint original — visão de longo prazo, não da Fase 1)

- **Open-Core**: versão self-hosted gratuita (community) vs. versão cloud hospedada
  (pay-as-you-go).
- **Pay-as-you-go**: sem mensalidade fixa; cobrança por operação (ex: chamada de API acima de
  um limite gratuito, dado de fonte paga repassado com margem).
- Ver `ROADMAP.md` para a tabela completa do modelo de negócio herdada do blueprint.
