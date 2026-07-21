param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("BeforeUpgrade", "CompleteUpgrade", "Rollback")]
    [string]$Mode,
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"
$ServiceName = "WeeklyReportAssistant"
$DataDir = Join-Path $env:ProgramData "WeeklyReportAssistant"
$RollbackDir = Join-Path $DataDir "upgrade-rollback"
$ProgramBackup = Join-Path $RollbackDir "program"
$DataBackup = Join-Path $RollbackDir "data"
$Marker = Join-Path $RollbackDir "upgrade.json"

function Stop-WeeklyReportService {
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service -and $service.Status -ne "Stopped") {
        Stop-Service -Name $ServiceName -Force
        $service.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
    }
}

function Wait-Ready {
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health/ready" -TimeoutSec 2
            $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
            if ($response.status -eq "ready" -and $service.Status -eq "Running") { return }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    throw "Service readiness check timed out"
}

function Restore-PreviousVersion {
    Stop-WeeklyReportService
    $isUpgrade = $false
    if (Test-Path $Marker) {
        $state = Get-Content $Marker -Raw | ConvertFrom-Json
        $isUpgrade = [bool]$state.is_upgrade
    }
    if ($isUpgrade -and (Test-Path $ProgramBackup)) {
        & robocopy.exe $ProgramBackup $InstallDir /MIR /R:2 /W:1 | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "Program rollback failed" }
        foreach ($name in @("app.db-wal", "app.db-shm", "app.db-journal")) {
            $sidecar = Join-Path $DataDir $name
            if (Test-Path $sidecar) { Remove-Item $sidecar -Force }
        }
        foreach ($item in Get-ChildItem $DataBackup -File -ErrorAction SilentlyContinue) {
            Copy-Item $item.FullName (Join-Path $DataDir $item.Name) -Force
        }
        $oldInstaller = Join-Path $InstallDir "installer\install_service.ps1"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $oldInstaller -InstallDir $InstallDir
        if ($LASTEXITCODE -ne 0) { throw "Previous service restart failed" }
    } else {
        $uninstallService = Join-Path $InstallDir "installer\uninstall_service.ps1"
        if (Test-Path $uninstallService) {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $uninstallService -InstallDir $InstallDir
        }
    }
}

if ($Mode -eq "BeforeUpgrade") {
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    $serviceWasRunning = $service -and $service.Status -eq "Running"
    try {
        Stop-WeeklyReportService
        $occupied = Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue
        if ($occupied) { throw "Port 8765 is already in use" }
        if (Test-Path $RollbackDir) { Remove-Item $RollbackDir -Recurse -Force }
        New-Item -ItemType Directory -Path $ProgramBackup -Force | Out-Null
        New-Item -ItemType Directory -Path $DataBackup -Force | Out-Null
        $existingExecutable = Join-Path $InstallDir "weekly-report-assistant.exe"
        $isUpgrade = Test-Path $existingExecutable
        if ($isUpgrade) {
            Copy-Item (Join-Path $InstallDir "*") $ProgramBackup -Recurse -Force
            foreach ($name in @("app.db", "model_settings.json", "model_api_key", "config.toml")) {
                $source = Join-Path $DataDir $name
                if (Test-Path $source) { Copy-Item $source $DataBackup -Force }
            }
        }
        @{ is_upgrade = $isUpgrade; created_at = [DateTime]::UtcNow.ToString("o") } |
            ConvertTo-Json | Set-Content -Path $Marker -Encoding UTF8
    } catch {
        if ($serviceWasRunning) { Start-Service -Name $ServiceName -ErrorAction SilentlyContinue }
        throw
    }
    exit 0
}

if ($Mode -eq "Rollback") {
    Restore-PreviousVersion
    exit 0
}

$Executable = Join-Path $InstallDir "weekly-report-assistant.exe"
$InstallService = Join-Path $InstallDir "installer\install_service.ps1"
try {
    & $Executable --migrate
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed" }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $InstallService -InstallDir $InstallDir
    if ($LASTEXITCODE -ne 0) { throw "Service installation failed" }
    Wait-Ready
    if (Test-Path $RollbackDir) { Remove-Item $RollbackDir -Recurse -Force }
} catch {
    Restore-PreviousVersion
    throw
}
