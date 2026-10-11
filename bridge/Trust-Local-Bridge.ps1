$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path 'certs\localhost.crt')) { throw 'Zuerst Setup.ps1 ausführen.' }
Write-Host 'Dieses Zertifikat gilt für die lokale Mythic-Walker-Bridge (localhost).'
Write-Host 'Es wird nur im Zertifikatsspeicher deines Windows-Benutzers hinterlegt.'
Write-Host 'Entfernen: Remove-Local-Trust.ps1. Private Schlüssel bleiben lokal.'
$answer = Read-Host 'Lokales Zertifikat vertrauen? Tippe JA'
if ($answer -cne 'JA') { Write-Host 'Abgebrochen.'; exit }
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2((Join-Path $PSScriptRoot 'certs\localhost.crt'))
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root','CurrentUser')
$store.Open('ReadWrite')
try { $store.Add($cert) } finally { $store.Close() }
Write-Host 'Vertrauen eingerichtet. Browser bei Bedarf neu starten.'
