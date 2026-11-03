# OTel Lab — FastAPI + MySQL + SigNoz

Projeto didático para gerar traces com uma aplicação FastAPI. O frontend envia `POST /api/items`; a API grava o nome no MySQL. A instrumentação OpenTelemetry cria spans da requisição HTTP e da consulta SQL, envia tudo ao OpenTelemetry Collector, e o Collector encaminha para o SigNoz via OTLP.

## Pré-requisitos

- Windows 10/11 com Docker Desktop ou Docker Engine dentro do WSL2.
- Docker Compose v2.
- Pelo menos 4 GB disponíveis para a instalação do SigNoz.

### Windows: recomendação

Para o SigNoz, a opção mais previsível é usar WSL2 com uma distribuição Linux e Docker Engine instalado dentro dela. A própria documentação do SigNoz alerta que o ClickHouse Keeper pode apresentar falhas no Docker Desktop sobre Windows. Se você já usa Docker Desktop, poderá executar o laboratório por PowerShell, mas prefira o WSL2 para o SigNoz.

No PowerShell, a instalação do WSL2 pode ser iniciada com:

```powershell
wsl --install
```

Depois de reiniciar e abrir o Ubuntu/WSL2, navegue até a pasta do projeto, por exemplo:

```bash
cd /mnt/c/Users/SEU_USUARIO/Downloads/otel-lab
```

## Subir o SigNoz

O SigNoz é instalado pelo método oficial atual, separado do laboratório, porque a composição interna dele pode mudar entre versões:

```bash
./signoz/install-signoz.sh
```

Também é possível iniciar o script a partir do PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\signoz\install-signoz.ps1
```

Se a política corporativa bloquear `Set-ExecutionPolicy` ou scripts não assinados, ignore o comando acima e execute diretamente no WSL2:

```powershell
wsl.exe bash -lc "cd /mnt/c/Projetos-Docker/otel-lab-manus && chmod +x signoz/install-signoz.sh && ./signoz/install-signoz.sh"
```

Troque o caminho `/mnt/c/Projetos-Docker/otel-lab-manus` pelo caminho real da pasta. Quando o Docker Engine estiver instalado dentro do WSL2, execute também o `docker compose` a partir do terminal Ubuntu/WSL2, para que o SigNoz e o laboratório usem o mesmo daemon Docker.

### Crie a conta de administrador antes de enviar telemetria

Este passo é obrigatório, não opcional. Acesse `http://localhost:8080` e crie a conta de
administrador. Enquanto isso não for feito, o SigNoz não tem organização, e o servidor OpAMP
recusa o registro do ingester com `cannot create agent without orgId`. Sem esse registro o
ingester nunca recebe a configuração do pipeline e **não abre a porta `4317`** — o coletor do
laboratório falha com `connection refused` ou `error reading server preface: EOF`.

Para verificar se o passo já foi concluído:

```bash
curl -s http://localhost:8080/api/v1/version   # espera-se "setupCompleted":true
```

### Endpoint OTLP

O `docker-compose.yml` já conecta o `otel-collector` à rede externa `signoz-network`, então o
ingester é alcançável pelo nome do container. O valor padrão em `.env.example` é
`signoz-ingester:4317`. Confirme o nome na sua instalação com:

```bash
docker ps | grep ingester
```

Evite `host.docker.internal` no WSL2 com Docker Engine: o nome resolve, mas o tráfego passa pela
publicação de porta do host e o diagnóstico fica confuso quando o ingester está sem configuração.

## Subir a aplicação

No PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

No WSL2, use os comandos equivalentes abaixo:

```bash
cp .env.example .env
# edite SIGNOZ_OTLP_ENDPOINT conforme a instalação do SigNoz
docker compose up --build
```

Abra `http://localhost:8000`, informe um valor e clique em **Salvar**. O dado aparecerá na lista e ficará persistido no MySQL.

## O que observar no SigNoz

Em **Services**, procure `fastapi-lab`. Uma requisição de criação deve mostrar spans HTTP da FastAPI e spans de banco gerados pela instrumentação do SQLAlchemy. Use a busca por serviço para filtrar `service.name = fastapi-lab`.

## Comandos úteis

```bash
docker compose logs -f app
docker compose logs -f otel-collector
docker compose down
docker compose down -v  # remove também os dados do MySQL
```

A rota também pode ser chamada diretamente:

```bash
curl -X POST http://localhost:8000/api/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"item via curl"}'
```

Para popular o dashboard com carga leve e sequencial, execute:

```bash
./load/generate.sh
```

O script roda por 10 minutos por padrão, alternando `POST` e `GET` a aproximadamente
1 requisicao por segundo. Para ajustar a duração, passe segundos como argumento, por
exemplo `./load/generate.sh 60`.
