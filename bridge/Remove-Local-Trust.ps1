$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path 'certs\localhost.crt')) { throw 'Kein lokales Bridge-Zertifikat gefunden.' }
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2((Join-Path $PSScriptRoot 'certs\localhost.crt'))
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root','CurrentUser')
$store.Open('ReadWrite')
try { $store.Remove($cert) } finally { $store.Close() }
Write-Host 'Lokales Bridge-Vertrauen entfernt.'
