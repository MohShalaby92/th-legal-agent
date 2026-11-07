# TH Legal Review Agent — installer for team members (Windows PowerShell)
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File .\setup-th-legal.ps1
param(
  [string]$RepoUrl = "https://github.com/CHANGE-ME/th-legal-agent.git",
  [string]$ProfileName = "th-legal"
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Say($ar, $en) { Write-Host "$ar" -ForegroundColor Cyan; if ($en) { Write-Host "   $en" -ForegroundColor DarkGray } }

Say "== تثبيت مساعد فريق التدقيق ==" "TH Legal Review Agent setup"

# 1) Hermes
if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
  Say "لم يتم العثور على Hermes على هذا الجهاز." "Hermes is not installed."
  $ans = Read-Host "هل تريد تثبيته الآن؟ (y/n)"
  if ($ans -ne "y") { Say "ثبّت تطبيق Hermes Desktop من https://hermes-agent.nousresearch.com ثم أعد تشغيل هذا الملف."; exit 1 }
  Invoke-Expression (Invoke-RestMethod https://hermes-agent.nousresearch.com/install.ps1)
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
}
hermes --version

# 2) Agent profile (from the team's private repository — Git will open a GitHub sign-in window the first time)
Say "تنزيل إعدادات المساعد من مستودع الفريق..." "Installing the agent profile from $RepoUrl"
$existing = (hermes profile list 2>$null | Select-String -SimpleMatch $ProfileName)
if ($existing) {
  hermes profile update $ProfileName
} else {
  hermes profile install $RepoUrl --name $ProfileName --alias -y
}

# 3) Make sure the privacy shield is on (installs its PDF/Word/Excel readers)
hermes -p $ProfileName plugins enable th-privacy-shield
hermes -p $ProfileName plugins list --plain --no-bundled

# 4) Engine — each member signs in with THEIR OWN account
Say "اختر محرك الذكاء الاصطناعي الخاص بك وسجّل الدخول بحسابك أنت:" "Pick your AI engine and sign in with your own account:"
Write-Host "   - Claude Opus 5.5  -> اختر المزوّد Anthropic ثم النموذج Claude Opus 5.5"
Write-Host "   - ChatGPT Sol 5.6 / Sol 6 -> اختر المزوّد OpenAI (ChatGPT / Codex sign-in) ثم النموذج المطلوب"
hermes -p $ProfileName model

Say "تم التثبيت ✅" "Done."
Say "للبدء: افتح تطبيق Hermes Desktop واختر الملف الشخصي th-legal، أو اكتب في الطرفية:  th-legal chat" "Start: Hermes Desktop -> profile th-legal, or run: th-legal chat"
Say "للتحديث لاحقًا:  hermes profile update th-legal" "Update later: hermes profile update th-legal"
