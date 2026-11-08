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
$HermesHome  = Join-Path $env:LOCALAPPDATA "hermes"
$THDir       = Join-Path $env:LOCALAPPDATA "TH-Legal"
$CdpPort     = 9222
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
  foreach ($p in @("$HermesHome\bin\hermes.cmd", "$HermesHome\bin\hermes.exe")) { if (Test-Path $p) { return $p } }
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
function Find-Browser {
  foreach ($p in @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
                   "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
                   "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe")) { if ($p -and (Test-Path $p)) { return $p } }
  return $null
}
function Find-Tesseract {
  foreach ($p in @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe", "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe")) { if (Test-Path $p) { return $p } }
  return $null
}
function Set-Cfg($hermesExe, $prof, $key, $value) {
  if ($prof) { & $hermesExe -p $prof config set $key $value | Out-Null } else { & $hermesExe config set $key $value | Out-Null }
  if ($LASTEXITCODE -ne 0) { Write-Host "warning: could not set $key" -ForegroundColor Yellow }
}

try {
  if (-not (Ask "سيتم تثبيت (أو تحديث) مساعد فريق التدقيق على هذا الجهاز.`n`nقد يستغرق التثبيت الأول من 10 إلى 20 دقيقة. اترك النافذة السوداء مفتوحة حتى تظهر رسالة الانتهاء.`n`nإذا كان تطبيق Hermes مفتوحًا فسيُغلق ثم يُفتح من جديد.`n`nهل تريد المتابعة؟")) { exit 0 }

  # 0) Close the app so the new privacy settings load cleanly
  if (-not $Test) { Get-Process -Name "Hermes" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue }

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
  $profileDir = Join-Path $HermesHome "profiles\$ProfileName"
  if (Test-Path (Join-Path $profileDir "distribution.yaml")) {
    Step "Updating the review agent..."
    & $hermes profile update $ProfileName -y
  } else {
    Step "Installing the review agent..."
    & $hermes profile install $RepoUrl --name $ProfileName --alias -y
  }
  if ($LASTEXITCODE -ne 0) { throw "Agent profile install/update failed (exit $LASTEXITCODE)." }
  $skillsDir = Join-Path $profileDir "skills\th-legal"

  # 3) Privacy shield in the profile AND in the main Hermes setup.
  #    The desktop app runs some agent work under the main setup, so the shield must be there too.
  Step "Enabling the privacy shield everywhere..."
  $rootPlugin = Join-Path $HermesHome "plugins\th-privacy-shield"
  New-Item -ItemType Directory -Force -Path (Split-Path $rootPlugin) | Out-Null
  if (Test-Path $rootPlugin) { Remove-Item -Recurse -Force $rootPlugin }
  Copy-Item -Recurse -Force (Join-Path $profileDir "plugins\th-privacy-shield") $rootPlugin
  foreach ($p in @($null, $ProfileName)) {
    $pa = if ($p) { @("-p", $p) } else { @() }
    # 'plugins enable' re-checks every Python package of Hermes; it fails while a download server
    # (often GitHub) is down. Never fake it in config.yaml: Hermes reverts unadmitted edits.
    for ($try = 1; $try -le 5; $try++) {
      & $hermes @pa plugins enable th-privacy-shield
      $lst = & $hermes @pa plugins list --plain --no-bundled
      if (($lst | Out-String) -match "(?m)^enabled\s+.*th-privacy-shield") { break }
      if ($try -eq 5) { throw "NETWORK: privacy shield could not be enabled in '$(if ($p) { $p } else { 'main setup' })'." }
      Write-Host "download problem - retrying in 60 s ($try/4)..." -ForegroundColor Yellow
      Start-Sleep -Seconds 60
    }
  }

  # 4) Same browser + approval settings in the main setup AND the profile (profile updates keep old values)
  Step "Applying browser and approval settings..."
  foreach ($p in @($null, $ProfileName)) {
    Set-Cfg $hermes $p "browser.cdp_url" "http://127.0.0.1:$CdpPort"
    Set-Cfg $hermes $p "browser.use_real_profile" "false"
    Set-Cfg $hermes $p "browser.inactivity_timeout" "1800"
    Set-Cfg $hermes $p "browser.command_timeout" "60"
  }
  $allow = "th *"
  foreach ($cfgPath in @((Join-Path $HermesHome "config.yaml"), (Join-Path $profileDir "config.yaml"))) {
    $cfgText = if (Test-Path $cfgPath) { [IO.File]::ReadAllText($cfgPath) } else { "" }
    $cfgText = $cfgText -replace "(?m)^  - python ~/AppData/Local/TH-Legal/th\.py \*\x0D?\n", ""   # v1.1.0 pre-release entry
    if ($cfgText -match "(?m)^  - th \*\s*$") { [IO.File]::WriteAllText($cfgPath, $cfgText, (New-Object System.Text.UTF8Encoding($false))); continue }
    if ($cfgText -match "(?m)^command_allowlist:[ \t\x0D]*$") {
      $cfgText = [regex]::Replace($cfgText, "(?m)^command_allowlist:[ \t\x0D]*$", "command_allowlist:`n  - $allow", 1)
    } elseif ($cfgText -notmatch "(?m)^command_allowlist:") {
      $cfgText = $cfgText.TrimEnd() + "`ncommand_allowlist:`n  - $allow`n"
    } else { Write-Host "note: command_allowlist has a custom format in $cfgPath; add '$allow' by hand"; continue }
    [IO.File]::WriteAllText($cfgPath, $cfgText, (New-Object System.Text.UTF8Encoding($false)))
  }

  # 5) The `th` command (same on every PC): launcher + tiny wrappers on the PATH Hermes already uses
  New-Item -ItemType Directory -Force -Path $THDir | Out-Null
  Copy-Item -Force (Join-Path $skillsDir "_launcher.py") (Join-Path $THDir "th.py")
  $binDir = Join-Path $HermesHome "bin"
  New-Item -ItemType Directory -Force -Path $binDir | Out-Null
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [IO.File]::WriteAllText((Join-Path $binDir "th"), "#!/bin/sh`nexec python ""`$LOCALAPPDATA/TH-Legal/th.py"" ""`$@""`n", $utf8)
  [IO.File]::WriteAllText((Join-Path $binDir "th.cmd"), "@python ""%LOCALAPPDATA%\TH-Legal\th.py"" %*`r`n", $utf8)

  # 6) Work browser: own Chrome/Edge window with a separate work profile + desktop shortcut
  Step "Preparing the work browser..."
  $browser = Find-Browser
  $firstBrowserSetup = $false
  if ($browser) {
    $oldProfile = Join-Path $env:USERPROFILE "TH-Chrome"
    $workProfile = if (Test-Path $oldProfile) { $oldProfile } else { Join-Path $THDir "browser" }
    if (-not (Test-Path $workProfile)) { $firstBrowserSetup = $true }
    @{ exe = $browser; profile_dir = $workProfile; port = $CdpPort } | ConvertTo-Json |
      Set-Content -Encoding UTF8 (Join-Path $THDir "work-browser.json")
    $lnkPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "TH Chrome (العمل).lnk"
    $tmpLnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "TH-Chrome-work.lnk"   # COM can't save Arabic names; rename after
    try {
      $ws = New-Object -ComObject WScript.Shell
      $sc = $ws.CreateShortcut($tmpLnk)
      $sc.TargetPath = $browser
      $sc.Arguments = "--remote-debugging-port=$CdpPort --user-data-dir=""$workProfile"" --no-first-run --no-default-browser-check https://manage.th-lawfirm.sa/dashboard https://drive.google.com/drive/my-drive"
      $sc.Description = "TH work browser - sign in once here; the review agent works in this window"
      $sc.IconLocation = "$browser,0"
      $sc.Save()
      Move-Item -Force -LiteralPath $tmpLnk -Destination $lnkPath
    } catch {
      Write-Host "warning: could not create the desktop shortcut ($($_.Exception.Message))" -ForegroundColor Yellow
      if (Test-Path $tmpLnk) { $lnkPath = $tmpLnk }
    }
  } else {
    Write-Host "Chrome/Edge not found - the agent will ask the user to install Chrome." -ForegroundColor Yellow
  }

  # 7) Local Arabic OCR for scanned documents (nothing is uploaded)
  Step "Installing local OCR (Arabic)..."
  if (-not (Find-Tesseract)) {
    & winget install --id tesseract-ocr.tesseract -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
  }
  $tess = Find-Tesseract
  $td = Join-Path $THDir "tessdata"
  New-Item -ItemType Directory -Force -Path $td | Out-Null
  Copy-Item -Force (Join-Path $skillsDir "th-local-docs\tessdata\ara.traineddata") $td -ErrorAction SilentlyContinue
  if ($tess) {
    Copy-Item -Force (Join-Path (Split-Path $tess) "tessdata\eng.traineddata") $td -ErrorAction SilentlyContinue
  } else {
    Write-Host "OCR could not be installed now; scanned pages will be flagged instead." -ForegroundColor Yellow
  }

  # 8) Open the app on this agent (+ the work browser the first time, to sign in)
  if (-not $Test) {
    & $hermes profile use $ProfileName
    if ($browser -and $firstBrowserSetup) { Start-Process $lnkPath }
    $lnk = Find-DesktopShortcut
    if ($lnk) { Start-Process $lnk } else { Start-Process $hermes -ArgumentList "desktop" }
  }

  $signin = if ($firstBrowserSetup) { "`n`nفُتحت نافذة «TH Chrome (العمل)»: سجّل الدخول فيها مرة واحدة إلى منصة التميمي والحمودي وإلى حساب جوجل الخاص بالعمل. يعمل المساعد داخل هذه النافذة، وتبقى تسجيلات الدخول محفوظة. لفتحها لاحقًا استخدم الاختصار على سطح المكتب." } else { "" }
  Tell "تم التثبيت بنجاح ✅$signin`n`nفي أول مرة فقط: اختر محرك الذكاء الاصطناعي الخاص بك في تطبيق Hermes وسجّل الدخول بحسابك أنت (Claude Opus 5.5 أو ChatGPT Sol 5.6 / Sol 6). سيرشدك المساعد خطوة بخطوة.`n`nللتحديث لاحقًا: شغّل هذا الملف مرة أخرى."
}
catch {
  Write-Host $_ -ForegroundColor Red
  if ("$($_.Exception.Message)" -like "NETWORK:*") {
    Tell "تعذّر تفعيل «حارس الخصوصية» بسبب مشكلة مؤقتة في الاتصال بخوادم التنزيل.`n`nلا تستخدم المساعد الآن. أعد تشغيل ملف الإعداد بعد قليل (نصف ساعة مثلًا).`n`nإن تكررت المشكلة أرسل هذا الملف إلى مسؤول الفريق:`n$Log" "Warning"
  } else {
    Tell "تعذّر إكمال التثبيت.`n`nأرسل هذا الملف إلى مسؤول الفريق:`n$Log`n`n($($_.Exception.Message))" "Error"
  }
  Stop-Transcript | Out-Null
  exit 1
}
Stop-Transcript | Out-Null
