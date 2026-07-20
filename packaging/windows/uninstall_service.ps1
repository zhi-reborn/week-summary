param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir,
    [switch]$RemoveData
)

$ErrorActionPreference = "Stop"
$ServiceName = "WeeklyReportAssistant"
$Executable = Join-Path $InstallDir "weekly-report-assistant.exe"
$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -ne "Stopped") {
        Stop-Service -Name $ServiceName -Force
        $service.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
    }
    if (Test-Path $Executable) {
        & $Executable --service remove
    }
    if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
        & sc.exe delete $ServiceName | Out-Null
    }
}

if ($RemoveData) {
    $DataDir = Join-Path $env:ProgramData "WeeklyReportAssistant"
    if (Test-Path $DataDir) {
        Remove-Item -Path $DataDir -Recurse -Force
    }
}
