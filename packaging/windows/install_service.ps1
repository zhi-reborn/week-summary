param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"
$ServiceName = "WeeklyReportAssistant"
$ServiceAccount = "NT SERVICE\WeeklyReportAssistant"
$DataDir = Join-Path $env:ProgramData "WeeklyReportAssistant"
$Executable = Join-Path $InstallDir "weekly-report-assistant.exe"

if (-not (Test-Path $Executable)) {
    throw "Service executable not found: $Executable"
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator privileges are required"
}

New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $DataDir "logs") -Force | Out-Null

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $existing) {
    & $Executable --service --startup auto install
    if ($LASTEXITCODE -ne 0) { throw "Failed to register Windows service" }
} elseif ($existing.Status -ne "Stopped") {
    Stop-Service -Name $ServiceName -Force
    $existing.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
}

$binaryPath = ('"{0}" --service' -f $Executable)
& sc.exe config $ServiceName binPath= $binaryPath start= auto obj= $ServiceAccount
if ($LASTEXITCODE -ne 0) { throw "Failed to configure service account" }
& sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/15000/none/0
if ($LASTEXITCODE -ne 0) { throw "Failed to configure recovery actions" }
& sc.exe failureflag $ServiceName 1
if ($LASTEXITCODE -ne 0) { throw "Failed to enable recovery actions" }

& icacls.exe $DataDir /inheritance:r /grant:r `
    "SYSTEM:(OI)(CI)F" `
    "Administrators:(OI)(CI)F" `
    "${ServiceAccount}:(OI)(CI)M" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to secure data directory" }
& icacls.exe $InstallDir /grant:r "${ServiceAccount}:(OI)(CI)RX" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to grant service read access" }

Start-Service -Name $ServiceName
(Get-Service -Name $ServiceName).WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
