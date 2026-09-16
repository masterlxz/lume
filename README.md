# Lume

Finance API open-source: centraliza, num serviço único, dados financeiros (mercado
BR/global, macroeconomia, cripto) hoje espalhados em fontes isoladas — ponto de partida do
projeto irmão [Anchor](https://github.com/masterlxz/anchor), que resolve isso de forma
específica pra si mesmo. Ver [`project/INDEX.md`](project/INDEX.md) pro histórico completo de
decisões (visão, arquitetura, roadmap, pendências).

## Arquitetura

| Componente | Stack | Path |
|---|---|---|
| Finance API | Python + FastAPI + PostgreSQL | [`api/`](api/) |
| Docs | Next.js + Fumadocs | [`docs/`](docs/) |

## Rodando localmente

Ambiente 100% via Docker — nada precisa ser instalado no host além do Docker.

```bash
cp api/.env.example api/.env
docker compose up --build
```

A API sobe em `http://localhost:8000`. Endpoint de exemplo (auth via header `X-API-Key`, chave
de dev em `api/.env.example`):

```bash
curl -H "X-API-Key: local-dev-key-change-me" http://localhost:8000/v1/macro-series/cdi
```

Testes automatizados (mockados, sem depender de rede real):

```bash
docker compose exec api pytest -v
```

`docker compose up` também sobe a documentação pública em `http://localhost:3000/docs`
(referência de endpoints gerada ao vivo a partir do `/openapi.json` da própria API, mais guias
de autenticação, cache e catálogo de fontes) — versão publicada em
[masterlxz.github.io/lume/docs](https://masterlxz.github.io/lume/docs/)
(deploy automático via `.github/workflows/deploy-docs.yml` a cada push em `docs/`/`api/app/`).

## Status

Projeto em desenvolvimento inicial (Fase 1 — Finance API). Roadmap completo,
decisões de arquitetura e o catálogo de fontes de dados em [`project/`](project/) — comece por
[`project/INDEX.md`](project/INDEX.md).

## Segurança

- Repositório público desde o primeiro commit — nunca commitar chave de API, connection string
  ou credencial (usar `.env`, sempre gitignored).
- Projeto em estágio inicial, não auditado — trate como software early-stage.

## Licença

MIT — ver [`LICENSE`](LICENSE).
