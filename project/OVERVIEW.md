# O que é o Lume

Lume é uma plataforma open-source de automação, finanças e gestão para o
empreendedor brasileiro. A visão completa (3 camadas: APIs/SDKs, Workspace web, módulo B3)
vem do blueprint original do projeto (`blueprint_plataforma_opensource.md.docx`, lido na
Sessão 1 e removido do repo depois de incorporado à documentação — ver `CONTEXT.md` e
`ROADMAP.md` para o conteúdo completo).

**MVP atual (decidido na Sessão 1)**: em vez de atacar as 3 camadas do blueprint de uma vez, o
ponto de partida é a **Finance API**, que alimenta um **Finance DB**
centralizado. A ideia nasce de um problema concreto: o projeto irmão
[Anchor](../../anchor) já resolve boa parte da coleta de dados financeiros (cotações B3,
cripto, macro, fundamentos) espalhada em ~12 scripts Python independentes, cada um falando com
uma fonte diferente e escrevendo direto no SQLite local do Anchor — funciona, mas fica preso a
um único consumidor e sem camada de confiabilidade compartilhada. O Lume deve virar
essa coleta um serviço único, confiável e documentado, exposto via API — que o próprio Anchor
passa a consumir (em vez de rodar o coletor localmente), e que qualquer outro projeto (ou
usuário externo, no modelo pay-as-you-go do blueprint) também pode consumir.

Stack: **Python + FastAPI + PostgreSQL**, self-host via Docker Compose (decidido na Sessão 2 —
ver `ARCHITECTURE.md`, seção "Decisões de Arquitetura em Aberto"). Documentação pública em
`docs/` — Next.js + Fumadocs (decidido na Sessão 7).

---

# Status Geral

```
Fase 1 — Finance API + Finance DB (MVP)          [x] Completa (8/8)
Fase 2 — Engine Fiscal (SEFAZ)                    [ ] Não iniciada
Fase 3 — Meta Cloud API & Automação (WhatsApp)    [ ] Não iniciada
Fase 4 — Workspace Web App                        [ ] Não iniciada
```

---

# Checklist antes do próximo release

**Fase 1 completa** — as 11 fontes do catálogo original (`CONTEXT.md`) estão todas portadas
(`api/`: BCB SGS, Yahoo Finance, CVM DFP+FII, cripto, B3 index stats, Yahoo Metais, bolsai, SEC
EDGAR), cache-through via Postgres, auth por API key, 162 testes automatizados passando. O
Anchor já consome a Finance API (migração híbrida, Sessão 7 — ver `PHASE.md` 1.7). Documentação
pública em `docs/` (Sessão 7 — ver `PHASE.md` 1.8). Esta seção será preenchida com um checklist
de release real quando o projeto sair do estágio de self-host/MVP (deploy público, domínio,
versão da API).
