# TH Legal Review Agent (مساعد فريق التدقيق)

A shareable **Hermes profile distribution**. Each team member installs it on their own PC, signs in with
their own AI engine, and uses it independently. You (the team lead) maintain this repo; members pull updates.

## What's inside
| Path | Purpose |
|---|---|
| `SOUL.md` | Agent persona & standing rules (Arabic, permission-first, privacy, finish ranges) |
| `config.yaml` | Privacy-hardened defaults (manual approvals, no title/background side-calls, no vision tools, visible browser) |
| `plugins/th-privacy-shield/` | On-device PII masking + Saudi ID/IBAN/phone/address validation + local unmasking |
| `skills/th-legal/*` | Workflows: session start, document review, missing data, range runner, platform map, Drive, iLovePDF, local extraction |
| `docs/` | Install guide page (Arabic) + `setup-th-legal.ps1` — publish this folder |
| `install/setup-th-legal.ps1` | Member installer (source copy; keep `docs/` copy in sync) |
| `tests/` | Synthetic-data tests + fake-LLM end-to-end privacy test |

## How the privacy shield works
1. Every tool result is masked as it enters the conversation (`transform_tool_result`).
2. The entire outbound LLM request is masked again right before it leaves the PC (`llm_request`
   middleware) — system prompt, user messages, tool results, tool args. Images/PDF/file parts are stripped.
   If masking ever errors, all text is replaced with a block notice (fail-closed).
3. Tokens inside arguments of *local* tools (browser, terminal, files) are swapped back to real values
   (`tool_request` middleware), so the agent can fill forms/edit files without seeing the data.
4. Vault of real values: `%LOCALAPPDATA%\hermes\profiles\th-legal\local\th-privacy\vault.bin`, DPAPI-encrypted.

Detected: Saudi NID / Iqama (with checksum), 700-unified, CR, IBAN (mod-97 + bank code), phones, e-mail,
passport, national address parts, long numbers (deed/case/contract with context), names (labels such as
المدعي:/السيد/المواطن/تم الرفع بواسطة, "بن/بنت" chains, a given-name lexicon `names_ar.txt`, and every
spelling variant of names already seen).

**Known limits (be honest with the team):** a name with no label, no "بن" chain and a first name missing
from `names_ar.txt` can slip through → add names to `names_ar.txt` (team-wide) or `/pii-name` (personal).
User-typed chat text is masked for the main model, but if Hermes compresses a very long conversation, the
compression call sees the history; tool results there are already masked, raw user-typed text is not —
so members must not paste personal data into chat. iLovePDF uploads leave the PC by policy.

## Run the tests
```
python tests/test_masker.py
python tests/test_plugin.py
```
End-to-end (no real AI, no network): start `python tests/fake_llm.py <log.jsonl> <out.txt>`, point a test
profile at `http://127.0.0.1:8765/v1` (`model.provider custom`), send a message with synthetic PII and
check the log contains no raw values.

## Publishing (live)
- Repo (private): https://github.com/MohShalaby92/th-legal-agent — add each member as a collaborator
  (Settings → Collaborators, read access). Their first install opens a GitHub sign-in window.
- Install guide: https://th-legal-guide.pages.dev (Cloudflare Pages project `th-legal-guide`, direct upload).
  Redeploy after changing `docs/`:
  `npx wrangler pages deploy docs --project-name th-legal-guide --branch master`
- Keep `install/setup-th-legal.ps1` and `docs/setup-th-legal.ps1` identical (UTF-8 with BOM, so Arabic
  shows correctly in Windows PowerShell).

## Releasing updates
Edit skills/SOUL/plugin → run tests → bump `version` in `distribution.yaml` → commit → `git tag vX.Y.Z` →
push with tags. Members run `hermes profile update th-legal` (their model choice and memory stay).
To push new `config.yaml` defaults, tell members to run `hermes profile update th-legal --force-config`
and then re-select their engine with `th-legal model`.
