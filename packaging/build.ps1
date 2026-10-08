# Build PiCore for Windows:  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
# 1. runs the tests  2. builds dist\PiCore with PyInstaller  3. self-tests the exe
# 4. if Inno Setup is installed, makes dist\PiCore-Setup-<version>.exe
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$version = (python -c "import picore; print(picore.__version__)").Trim()
Write-Host "Building PiCore $version"

python -m pytest -q -p no:warnings
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

python -m PyInstaller packaging\picore.spec --noconfirm --log-level WARN
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

if (Get-ChildItem dist\PiCore -Recurse -Filter picore.config.json) { throw "API key file leaked into the build" }
foreach ($f in Get-ChildItem assets\fonts -Filter *.tt?) {
    if ($f.Name -ne "ShotengaiDemo.otf" -and -not (Test-Path "dist\PiCore\_internal\assets\fonts\$($f.Name)")) {
        throw "Font missing from build: $($f.Name) (add it to FONTS in picore.spec)"
    }
}

$report = Join-Path $env:TEMP "picore-selftest.json"
Remove-Item $report -ErrorAction SilentlyContinue
$env:PICORE_SELFTEST = $report
Start-Process dist\PiCore\PiCore.exe -Wait
Remove-Item Env:PICORE_SELFTEST
$r = Get-Content $report -Encoding utf8 | ConvertFrom-Json
if ($r.solve -ne "x = 2" -or -not $r.assets -or -not $r.storage -or $r.explore -ne "Quadratic" -or
    -not $r.diagnosis.StartsWith("Calculus") -or -not $r.equiv.StartsWith("Equivalent")) {
    throw "Self-test failed: $(Get-Content $report)"
}
Write-Host "Self-test passed"

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
          "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
    & $iscc "/DAppVersion=$version" packaging\installer.iss
    Write-Host "Installer: dist\PiCore-Setup-$version.exe"
} else {
    Write-Host "Inno Setup not found, skipping installer (winget install JRSoftware.InnoSetup). App folder: dist\PiCore"
}
