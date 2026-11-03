$ErrorActionPreference = "Stop"

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
  Write-Error "WSL2 não foi encontrado. Instale-o com: wsl --install"
}

$projectPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$drive = $projectPath.Substring(0, 1).ToLower()
$rest = $projectPath.Substring(2).Replace('\', '/')
$wslPath = "/mnt/$drive$rest"

Write-Host "Executando a instalação do SigNoz dentro do WSL2..."
wsl.exe bash -lc "cd '$wslPath' && chmod +x signoz/install-signoz.sh && ./signoz/install-signoz.sh"
