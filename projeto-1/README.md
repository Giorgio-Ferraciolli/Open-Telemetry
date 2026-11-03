# Tutorial prático de OpenTelemetry

Stack completa de observabilidade rodando localmente com Docker Compose. Tem 2 microserviços (Python + Node.js) instrumentados com OpenTelemetry, mandando traces, métricas e logs pra um Collector que distribui pra Tempo, Prometheus e Loki — tudo visualizado no Grafana.

Foi construído como um tutorial, em 8 etapas, pra entender OTel na prática.

## Arquitetura

```
                      ┌─────────────┐         ┌─────────────┐
   curl/load-gen ──▶  │ api-python  │ ──HTTP─▶│  api-node   │
                      │  (FastAPI)  │         │  (Express)  │
                      └──────┬──────┘         └──────┬──────┘
                             │ OTLP gRPC             │ OTLP gRPC
                             ▼                       ▼
                      ┌────────────────────────────────────────┐
                      │         OpenTelemetry Collector        │
                      │   recebe → processa → exporta          │
                      └────┬───────────┬─────────┬────────┬────┘
                           │           │         │        │
                           ▼           ▼         ▼        ▼
                        Tempo      Prometheus  Loki   arquivo
                       (traces)   (métricas)  (logs)  (fan-out)
                           │           │         │
                           └───────────┴─────────┘
                                      │
                                   Grafana
                                (UI única)
```

A graça do OTel está nessa separação: as aplicações **só conhecem o Collector** (falam um protocolo chamado OTLP). Quem decide pra onde mandar (Tempo? Datadog? New Relic?) é o Collector. Trocar de backend não exige mexer nas apps.

## Pré-requisitos

- Docker + Docker Compose
- Portas livres: `3000`, `3100`, `3200`, `4317`, `4318`, `8001`, `8002`, `8888`, `8889`, `9090`, `13133`
- ~2 GB de RAM disponível

## Como subir

```bash
docker compose up -d --build
```

Da primeira vez vai demorar uns minutinhos (build das imagens Python + Node). Depois sobe em ~10s.

Pra verificar se subiu tudo:

```bash
docker compose ps          # devem aparecer 6 containers "Up"
curl http://localhost:8001 # api-python
curl http://localhost:8002 # api-node
```

## Como usar

### 1. Gera tráfego sintético

```bash
bash load/generate.sh 30   # gera 30 segundos de requisições variadas
```

Isso enche a stack com dados pra você explorar.

### 2. Abre o Grafana

http://localhost:3000 (login não pede — modo anônimo ligado pra simplicidade do tutorial)

### 3. Roteiro de exploração

**Ver um trace distribuído** (uma requisição atravessando os 2 serviços)

1. Menu lateral → **Explore**
2. No topo, escolhe o datasource **Tempo**
3. Aba **Search** → **Service Name** = `api-python` → **Span Name** = `GET /checkout/{pid}` → **Run query**
4. Clica num resultado da lista
5. Vai abrir uma timeline mostrando: api-python → httpx → api-node, com cores por serviço

**Ver métricas customizadas**

1. **Explore** → datasource **Prometheus**
2. Cola: `histogram_quantile(0.95, sum by (le) (rate(app_checkout_duration_milliseconds_bucket[5m])))`
3. Vê o p95 da duração do checkout em tempo real

**Pular do log pro trace**

1. **Explore** → datasource **Loki**
2. Query: `{service_name="api-python"}`
3. Clica em qualquer log → expande os campos detalhados
4. O label `trace_id` aparece como link → clica e abre o trace correspondente no Tempo

**Ver o ServiceGraph**

1. **Explore** → datasource **Tempo** → aba **Service Graph**
2. Aparece um grafo: `api-python → api-node` com setas indicando taxa e latência

## Endpoints

| Serviço | URL | O que tem |
|---|---|---|
| Grafana | http://localhost:3000 | UI de tudo |
| Prometheus | http://localhost:9090 | métricas (raw) |
| Tempo | http://localhost:3200 | traces (raw) |
| Loki | http://localhost:3100 | logs (raw) |
| api-python | http://localhost:8001 | rotas: `/`, `/products`, `/products/{id}`, `/slow`, `/broken`, `/checkout/{id}` |
| api-node | http://localhost:8002 | rotas: `/`, `/stock/{id}` |
| Collector health | http://localhost:13133 | health check |
| Collector internal | http://localhost:8888/metrics | auto-observabilidade do Collector |
| Collector pipeline | http://localhost:8889/metrics | métricas das apps em formato Prometheus |

## Roteiro das 8 etapas

Cada etapa adiciona uma camada. Os arquivos estão organizados por responsabilidade:

| # | Etapa | Arquivos principais |
|---|---|---|
| 1 | Estrutura | `docker-compose.yml` |
| 2 | Backend (Tempo, Prometheus, Loki, Grafana) | `tempo/`, `prometheus/`, `loki/`, `grafana/` |
| 3 | OpenTelemetry Collector | `collector/config.yaml` |
| 4 | Primeiro serviço (Python + auto-instrumentação) | `services/api-python/main.py` |
| 5 | Segundo serviço (Node) + trace distribuído | `services/api-node/index.js` |
| 6 | Spans manuais, atributos, eventos, baggage | `services/api-python/main.py` (rota `/checkout`) |
| 7 | Métricas de negócio + correlação log↔trace | `services/api-python/main.py`, `services/api-node/index.js` |
| 8 | Filter, redact, tail sampling, fan-out | `collector/config.yaml` |

## Comandos úteis

```bash
# Subir tudo
docker compose up -d --build

# Subir só uma parte
docker compose up -d otel-collector

# Ver telemetria fluindo (debug exporter mostra batches passando)
docker compose logs -f otel-collector

# Logs de um serviço específico
docker logs -f api-python
docker logs -f api-node

# Reiniciar um serviço (após mudar config)
docker compose restart prometheus

# Reconstruir uma imagem após mexer em main.py / index.js
docker compose up -d --build api-python

# Gerar tráfego
bash load/generate.sh           # loop infinito (Ctrl+C pra parar)
bash load/generate.sh 60        # roda por 60 segundos

# Parar mantendo dados
docker compose down

# Parar e apagar tudo (volumes inclusive)
docker compose down -v

# Inspecionar o arquivo de fan-out (Etapa 8)
ls -la collector/output/
head -1 collector/output/traces.jsonl | python3 -m json.tool
```

## Estrutura do projeto

```
.
├── docker-compose.yml
├── README.md
├── collector/
│   ├── config.yaml              # config do OTel Collector
│   └── output/                  # destino do file exporter (fan-out)
├── tempo/
│   └── tempo.yaml
├── prometheus/
│   └── prometheus.yml
├── loki/
│   └── loki-config.yaml
├── grafana/
│   └── provisioning/
│       └── datasources/
│           └── datasources.yaml # configura datasources e correlações
├── services/
│   ├── api-python/              # FastAPI + OpenTelemetry SDK
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── api-node/                # Express + OpenTelemetry SDK
│       ├── index.js
│       ├── tracing.js           # setup do OTel (carregado via --require)
│       ├── package.json
│       └── Dockerfile
└── load/
    └── generate.sh              # gerador de tráfego com curl
```

## Troubleshooting

**"Não vejo nenhum trace no Grafana"**

```bash
docker compose logs otel-collector | grep -i error
docker compose logs api-python | tail -20
```

Confirma também que tá gerando tráfego: `curl http://localhost:8001/checkout/1` deve retornar JSON com produto e estoque.

**"Loki não retorna nada"**

Loki demora ~10s no startup. Tenta de novo. Se persistir:

```bash
curl http://localhost:3100/ready
```

Deve retornar `ready` (sem 503).

**"Configurei algo no `prometheus.yml` mas Prometheus não pegou"**

A `--web.enable-lifecycle` não tá habilitada. Reinicia o container:

```bash
docker compose restart prometheus
```

**"Mudei o `main.py` da api-python e nada mudou"**

Precisa rebuildar a imagem (não tem volume mount no código):

```bash
docker compose up -d --build api-python
```

**"Quero apagar tudo e começar do zero"**

```bash
docker compose down -v
rm -rf collector/output/*
docker compose up -d --build
```

## Próximos passos pra estudar

- **TraceQL** — linguagem de query do Tempo. Filtros como `{ duration > 500ms && status = error }` são poderosos.
- **OTTL** — linguagem que o Collector usa nos processors `filter` e `transform`. Vai além do que mostrei na Etapa 8.
- **Service graphs e RED metrics** — o `metrics_generator` do Tempo gera métricas automáticas dos traces (rate, errors, duration).
- **Coletor em Kubernetes** — padrões "sidecar" vs "gateway", e o operator do OTel.
- **Auto-instrumentação em outras linguagens** — Java tem agente JVM completíssimo, Go é mais manual, .NET tem boa cobertura.
