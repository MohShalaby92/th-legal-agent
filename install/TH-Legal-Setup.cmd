<# : TH Legal Review Agent - one-click installer (this line and the next block are for cmd.exe)
@echo off
title TH Legal Review Agent - Setup
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ([IO.File]::ReadAllText('%~f0', [Text.Encoding]::UTF8))"
exit /b
#>
# ---------------------------------------------------------------------------------------------
# Everything below is PowerShell. Double-click this file to install or update the agent.
# ---------------------------------------------------------------------------------------------
$ErrorActionPreference = "Continue"   # native tools write progress to stderr; we check exit codes instead
$RepoUrl     = "https://github.com/MohShalaby92/th-legal-agent.git"
$ProfileName = "th-legal"
$Test        = $env:TH_SETUP_TEST -eq "1"   # developer test mode: no dialogs, no default switch, no launch
$Log         = Join-Path $env:LOCALAPPDATA "TH-Legal-Setup.log"
Start-Transcript -Path $Log -Force | Out-Null
Add-Type -AssemblyName System.Windows.Forms

function Ask($text) {
  if ($Test) { return $true }
  $r = [System.Windows.Forms.MessageBox]::Show($text, "مساعد فريق التدقيق", "YesNo", "Question",
        "Button1", [System.Windows.Forms.MessageBoxOptions]::RtlReading -bor [System.Windows.Forms.MessageBoxOptions]::RightAlign)
  return $r -eq "Yes"
}
function Tell($text, $icon = "Information") {
  if ($Test) { Write-Host "[dialog] $text"; return }
  [void][System.Windows.Forms.MessageBox]::Show($text, "مساعد فريق التدقيق", "OK", $icon,
        "Button1", [System.Windows.Forms.MessageBoxOptions]::RtlReading -bor [System.Windows.Forms.MessageBoxOptions]::RightAlign)
}
function Step($t) { Write-Host ""; Write-Host ">> $t" -ForegroundColor Cyan }
function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
}
function Find-Hermes {
  Refresh-Path
  $c = Get-Command hermes -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($p in @("$env:LOCALAPPDATA\hermes\bin\hermes.cmd", "$env:LOCALAPPDATA\hermes\bin\hermes.exe")) { if (Test-Path $p) { return $p } }
  return $null
}
function Find-DesktopShortcut {
  $dirs = @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("CommonPrograms"), [Environment]::GetFolderPath("Desktop"))
  foreach ($d in $dirs) {
    $s = Get-ChildItem -Path $d -Recurse -Filter "Hermes*.lnk" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($s) { return $s.FullName }
  }
  return $null
}

try {
  if (-not (Ask "سيتم تثبيت (أو تحديث) مساعد فريق التدقيق على هذا الجهاز.`n`nقد يستغرق التثبيت الأول من 10 إلى 20 دقيقة. اترك النافذة السوداء مفتوحة حتى تظهر رسالة الانتهاء.`n`nهل تريد المتابعة؟")) { exit 0 }

  # 1) Hermes (the app that runs the agent)
  $hermes = Find-Hermes
  if (-not $hermes -or -not (Find-DesktopShortcut)) {
    Step "Installing Hermes + desktop app (first time only, please wait)..."
    $installer = Invoke-RestMethod "https://hermes-agent.nousresearch.com/install.ps1"
    & ([scriptblock]::Create($installer)) -NonInteractive -IncludeDesktop
    $hermes = Find-Hermes
    if (-not $hermes) { throw "Hermes was not found after installation." }
  } else {
    Step "Hermes is already installed: $hermes"
  }

  # 2) The agent profile from the team repository (public, no sign-in needed)
  $profileDir = Join-Path $env:LOCALAPPDATA "hermes\profiles\$ProfileName"
  if (Test-Path (Join-Path $profileDir "distribution.yaml")) {
    Step "Updating the review agent..."
    & $hermes profile update $ProfileName -y
  } else {
    Step "Installing the review agent..."
    & $hermes profile install $RepoUrl --name $ProfileName --alias -y
  }
  if ($LASTEXITCODE -ne 0) { throw "Agent profile install/update failed (exit $LASTEXITCODE)." }

  # 3) Privacy shield on + its document readers prepared
  Step "Preparing the privacy shield..."
  & $hermes -p $ProfileName plugins list --plain --no-bundled
  if ($LASTEXITCODE -ne 0) { throw "Privacy shield check failed (exit $LASTEXITCODE)." }

  # 4) Open the app on this agent
  if (-not $Test) {
    & $hermes profile use $ProfileName
    $lnk = Find-DesktopShortcut
    if ($lnk) { Start-Process $lnk } else { Start-Process $hermes -ArgumentList "desktop" }
  }

  Tell "تم التثبيت بنجاح ✅`n`nسيفتح تطبيق Hermes الآن على «مساعد فريق التدقيق».`n`nفي أول مرة فقط: اختر محرك الذكاء الاصطناعي الخاص بك وسجّل الدخول بحسابك أنت (Claude Opus 5.5 أو ChatGPT Sol 5.6 / Sol 6). سيرشدك المساعد خطوة بخطوة.`n`nللتحديث لاحقًا: شغّل هذا الملف مرة أخرى."
}
catch {
  Write-Host $_ -ForegroundColor Red
  Tell "تعذّر إكمال التثبيت.`n`nأرسل هذا الملف إلى مسؤول الفريق:`n$Log`n`n($($_.Exception.Message))" "Error"
  Stop-Transcript | Out-Null
  exit 1
}
Stop-Transcript | Out-Null
