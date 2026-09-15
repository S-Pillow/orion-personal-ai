@echo off
setlocal EnableExtensions

set "P404A_PS1=%~dp0p4-04a-hermes-audio-gateway.ps1"

if not exist "%P404A_PS1%" (
  echo P4-04A PREFLIGHT FAIL: wrapper not found: %P404A_PS1%
  exit /b 2
)

echo [1/3] Parse-checking PowerShell wrapper...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$errors=$null; $tokens=$null; [System.Management.Automation.Language.Parser]::ParseFile($env:P404A_PS1,[ref]$tokens,[ref]$errors) ^> $null; if($errors.Count -gt 0){ $errors ^| ForEach-Object { Write-Error $_.Message }; exit 2 }; Write-Host 'P4-04A POWERSHELL PARSE PASS'"
if errorlevel 1 (
  echo P4-04A PREFLIGHT FAIL: PowerShell parse check failed.
  exit /b 2
)

echo [2/3] Running patcher self-test in a fresh PowerShell process...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%P404A_PS1%" -Action SelfTest
if errorlevel 1 (
  echo P4-04A PREFLIGHT FAIL: self-test failed.
  exit /b 2
)

echo [3/3] Verifying installed Hermes source identity without modifying it...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%P404A_PS1%" -Action Verify
set "VERIFY_RC=%ERRORLEVEL%"

if "%VERIFY_RC%"=="0" (
  echo P4-04A PREFLIGHT PASS: installed target is already patched and verified.
  exit /b 0
)

if "%VERIFY_RC%"=="3" (
  echo P4-04A PREFLIGHT PASS: accepted Hermes source identity verified and remains unpatched.
  exit /b 0
)

echo P4-04A PREFLIGHT FAIL: installed Hermes source did not match an accepted state. Exit=%VERIFY_RC%
exit /b %VERIFY_RC%
