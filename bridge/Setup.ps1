$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'Mythic Walker - Setup (Python 3.11-3.13, Windows 64-bit)'
$launcher = Get-Command py -ErrorAction SilentlyContinue
if (!$launcher) { throw 'Python-Launcher py fehlt. Installiere Python 3.13 (64-bit) inklusive Launcher.' }

# The default Python only runs this dependency-free bootstrap. Bridge packages
# are installed exclusively with the explicitly selected compatible runtime.
$runtimeJson = & $launcher.Source -3 .\python_runtime.py --launcher $launcher.Source
if ($LASTEXITCODE -ne 0) { throw 'Keine passende Python-Version gefunden. Installiere Python 3.13 (64-bit, Standard-Build) und starte Setup erneut.' }
$runtime = ($runtimeJson -join "`n") | ConvertFrom-Json
Write-Host ('Ausgewaehlt: Python ' + ($runtime.version -join '.') + ' / ' + $runtime.executable)

$environmentPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$reuseEnvironment = $false
if (Test-Path $environmentPython) {
    try {
        & $environmentPython .\python_runtime.py --check 2>$null | Out-Null
        $reuseEnvironment = ($LASTEXITCODE -eq 0)
    } catch { $reuseEnvironment = $false }
}
if ((Test-Path '.venv') -and !$reuseEnvironment) {
    $backup = '.venv-before-fix-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6)
    Move-Item -LiteralPath '.venv' -Destination $backup
    Write-Host ('Unpassende Umgebung gesichert: ' + $backup)
}
if (!$reuseEnvironment) {
    & $runtime.executable -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Die Python-Umgebung konnte nicht angelegt werden.' }
}
& $environmentPython .\python_runtime.py --check
if ($LASTEXITCODE -ne 0) { throw 'Python-Version der Umgebung ist unpassend. Installation abgebrochen.' }

# regex must use a prebuilt wheel; do not request a C++ build on the user's PC.
& $environmentPython -m pip install --only-binary=regex -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Abhaengigkeiten konnten nicht installiert werden. Bitte die Meldungen oberhalb pruefen.' }
& $environmentPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Abhaengigkeitspruefung fehlgeschlagen.' }
& $environmentPython server.py --generate-cert
if ($LASTEXITCODE -ne 0) { throw 'Zertifikat konnte nicht erzeugt werden.' }
Write-Host 'Fertig. Weiter: Trust-Local-Bridge.ps1, danach Start-Bridge.cmd'
