$ErrorActionPreference = 'Stop'
$Installer = Join-Path $PSScriptRoot 'scripts/install.py'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $Installer
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $Installer
} else {
    throw 'Instalá Python 3.11 o posterior desde python.org y volvé a ejecutar el instalador.'
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
