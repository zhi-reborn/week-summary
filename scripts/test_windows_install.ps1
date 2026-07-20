param(
    [Parameter(Mandatory = $true)]
    [string]$Installer,
    [switch]$RemoveTestData
)

$ErrorActionPreference = "Stop"
$ServiceName = "WeeklyReportAssistant"
$Root = Split-Path -Parent $PSScriptRoot
$Fixture = Join-Path $Root "tests\fixtures\docx\plain_placeholder.docx"
$Installer = (Resolve-Path $Installer).Path
Add-Type -AssemblyName System.Net.Http

function Wait-Ready {
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8765/api/health/ready" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    throw "Readiness timed out"
}

function Invoke-Workflow {
    $task = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/api/tasks" `
        -ContentType "application/json" -Body '{"name":"windows-install-test"}'
    $client = [Net.Http.HttpClient]::new()
    $form = [Net.Http.MultipartFormDataContent]::new()
    try {
        $reports = [Net.Http.ByteArrayContent]::new([Text.Encoding]::UTF8.GetBytes("张三周报`n完成A`n`n李四周报`n完成B"))
        $template = [Net.Http.ByteArrayContent]::new([IO.File]::ReadAllBytes($Fixture))
        $form.Add($reports, "reports", "reports.txt")
        $form.Add($template, "template", "template.docx")
        $upload = $client.PostAsync("http://127.0.0.1:8765/api/tasks/$($task.id)/inputs", $form).Result
        if (-not $upload.IsSuccessStatusCode) { throw "Upload failed: $($upload.StatusCode)" }
    } finally {
        $form.Dispose()
        $client.Dispose()
    }
    foreach ($path in @("people/detect", "people/confirm", "template/detect", "template/confirm")) {
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/api/tasks/$($task.id)/$path" | Out-Null
    }
}

& $Installer /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
if ($LASTEXITCODE -ne 0) { throw "Installation failed" }
Wait-Ready
if ((Get-Service $ServiceName).Status -ne "Running") { throw "Service is not running" }
Invoke-Workflow

& $Installer /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
if ($LASTEXITCODE -ne 0) { throw "Upgrade failed" }
Wait-Ready

$Uninstaller = Get-ChildItem "${env:ProgramFiles}\WeeklyReportAssistant\unins*.exe" | Select-Object -First 1
if (-not $Uninstaller) { throw "Uninstaller not found" }
& $Uninstaller.FullName /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
if ($LASTEXITCODE -ne 0) { throw "Uninstall failed" }
if (Get-Service $ServiceName -ErrorAction SilentlyContinue) { throw "Service still exists" }
$DataDir = Join-Path $env:ProgramData "WeeklyReportAssistant"
if (-not (Test-Path $DataDir)) { throw "Uninstall should retain data by default" }
if ($RemoveTestData) { Remove-Item $DataDir -Recurse -Force }

Write-Output "WINDOWS_INSTALL_OK service=running health=200 workflow=passed upgrade=passed uninstall=passed"
