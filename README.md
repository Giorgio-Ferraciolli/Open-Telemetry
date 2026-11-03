# Open-Telemetry

Repositório de estudos práticos de **OpenTelemetry** e observabilidade.

## Projetos

| Pasta | Descrição |
|-------|-----------|
| [`projeto-1`](./projeto-1) | Stack LGTM (Loki, Grafana, Tempo, Prometheus) com OpenTelemetry Collector e 2 microserviços instrumentados (Python/FastAPI e Node.js/Express), tudo via Docker Compose. |

## Como usar

Cada projeto é independente. Entre na pasta e siga o README dela:

```bash
cd projeto-1
docker compose up -d
```

Depois acesse o Grafana em http://localhost:3000.

## Pré-requisitos

- Docker + Docker Compose
