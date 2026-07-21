$ErrorActionPreference = "Stop"

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "Windows installer must be built on Windows"
}
if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64") {
    throw "Windows installer must be built on x86-64 Windows"
}

$Root = Split-Path -Parent $PSScriptRoot
$Version = (Get-Content (Join-Path $Root "VERSION") -Raw).Trim()
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = (Get-Command py.exe -ErrorAction Stop).Source
    $PythonArgs = @("-3.12")
} else {
    $PythonArgs = @()
}

& $Python @PythonArgs (Join-Path $Root "scripts\build_frontend.py")
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
& $Python @PythonArgs (Join-Path $Root "scripts\build_backend.py")
if ($LASTEXITCODE -ne 0) { throw "Backend bundle build failed" }

$SignTool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
$Certificate = $env:WRA_SIGN_CERT_PATH
$CertificatePassword = $env:WRA_SIGN_CERT_PASSWORD
$BundleExe = Join-Path $Root "dist\weekly-report-assistant\weekly-report-assistant.exe"
if ($Certificate) {
    if (-not $SignTool) { throw "signtool.exe is required for configured signing" }
    & $SignTool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f $Certificate /p $CertificatePassword $BundleExe
    if ($LASTEXITCODE -ne 0) { throw "Bundle signing failed" }
    $SigningStatus = "signed"
} else {
    $SigningStatus = "not_configured"
}

$Iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $Iscc) {
    $candidate = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    if (Test-Path $candidate) { $Iscc = $candidate }
}
if (-not $Iscc) { throw "ISCC.exe (Inno Setup 6) was not found" }
& $Iscc "/DMyAppVersion=$Version" (Join-Path $Root "packaging\windows\weekly-report-assistant.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup build failed" }

$Installer = Join-Path $Root "dist\installers\WeeklyReportAssistant-$Version-windows-x64.exe"
if ($Certificate) {
    & $SignTool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f $Certificate /p $CertificatePassword $Installer
    if ($LASTEXITCODE -ne 0) { throw "Installer signing failed" }
}
if (-not (Test-Path $Installer)) { throw "Installer output is missing: $Installer" }
Write-Output "WINDOWS_BUILD_OK installer=$Installer signing=$SigningStatus"
