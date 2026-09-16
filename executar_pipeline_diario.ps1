$Projeto = $PSScriptRoot
$Python = Join-Path $Projeto ".venv\Scripts\python.exe"
$Script = Join-Path $Projeto "atualizar_fiis.py"
$PastaLogs = Join-Path $Projeto "logs"

# Garante que a pasta de logs exista
New-Item -ItemType Directory -Path $PastaLogs -Force | Out-Null

# Cria um arquivo diferente para cada execucao
$DataHora = Get-Date -Format "yyyy-MM-dd_HHmmss"
$ArquivoLog = Join-Path $PastaLogs "pipeline_$DataHora.log"

Set-Location $Projeto

"============================================================" | Tee-Object -FilePath $ArquivoLog
"FII INTELLIGENCE - EXECUCAO AUTOMATICA" | Tee-Object -FilePath $ArquivoLog -Append
"Inicio: $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')" | Tee-Object -FilePath $ArquivoLog -Append
"============================================================" | Tee-Object -FilePath $ArquivoLog -Append

& $Python $Script 2>&1 | Tee-Object -FilePath $ArquivoLog -Append

$CodigoSaida = $LASTEXITCODE

"============================================================" | Tee-Object -FilePath $ArquivoLog -Append
"Fim: $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')" | Tee-Object -FilePath $ArquivoLog -Append
"Codigo de saida: $CodigoSaida" | Tee-Object -FilePath $ArquivoLog -Append
"============================================================" | Tee-Object -FilePath $ArquivoLog -Append

exit $CodigoSaida