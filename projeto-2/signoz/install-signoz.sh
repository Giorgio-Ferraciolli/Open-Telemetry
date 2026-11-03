#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname "$0")/deployment"
cd "$(dirname "$0")/deployment"
if ! command -v foundryctl >/dev/null 2>&1; then
  echo "Instalando foundryctl..."
  curl -fsSL https://signoz.io/foundry.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi
cat > casting.yaml <<'YAML'
apiVersion: v1alpha1
kind: Installation
metadata:
  name: signoz
spec:
  deployment:
    flavor: compose
    mode: docker
YAML
foundryctl cast -f casting.yaml
cat <<'INFO'
SigNoz iniciado. Abra http://localhost:8080.
Configure SIGNOZ_OTLP_ENDPOINT no .env do projeto para apontar ao endpoint OTLP gRPC do coletor do SigNoz (4317), depois reinicie o laboratório.
INFO
