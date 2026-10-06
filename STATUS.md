# STATUS.md — current state (update with every state-changing commit)

Last verified: 2026-10-06 (desktop session, against git log + full test run)

## Spec
- **draft-04** (6b1b2e7): harness-visible = workspace root (jimy-r probe), cross-volume
  move sequence, visibility canary SHOULD. 37 behavior tests green.
- draft-03 closed Q1 (lockfile canonical; source = declared/resolved split, update-fetch
  rule) and Q3 (per-skill update normative), added the interop appendix.
- c20fe89: section 4.3 verify-then-move ordering (James Ross timing gap).

## Threads
- **#588 (agentskills Ideas)** — owned by the **bot surface**. Last: vhsgreed draft-03
  announcement (10-02). jimy-r engaged (install-side pushback, answered).
- **#283 (vercel-labs/skills)** — last: vhsgreed pitch (10-01). Vercel silent; collaborator
  quuu said "WIP" in Feb 2026, so treat the neutral-spec window as time-boxed.
- Watchers: cron `3beeb29e3517` (#588) and `86185fc96d28` (#283), both every 2h,
  monitor-gated, main model, deliver=local (no channel connected yet).

## Open decisions
- **Q4 governance home** (open in-thread). Desktop recommendation: donate the spec to
  agentskills/agentskills as a companion spec once draft-05 stabilizes; this repo keeps the
  reference implementation. Needs Karl's decision before any thread post.
- **Local model setup** (benchmark running 2026-10-06): gemma4:26b is MoE A4B (128 experts,
  8 used); qwen3-coder:30b (A3B), gemma4:e2b/e4b/12b all on disk. gemma4:26b-agentic
  (num_ctx 65536) fixed the silent-truncation defect but agentic cron runs exceed the 180s
  inactivity limit on the geekom iGPU; watch jobs run on the main model meanwhile.

## Loose-thread audit (2026-10-06, desktop session)
- **Attribution check (Karl's request): all five search hits were FALSE POSITIVES** — none
  refer to vhsgreed/skill-lock. The X "hot take" (poteto, Feb 2026), the explainx.ai blog,
  and Vercel issue #542 are all about Vercel's project-level `skills-lock.json` (npx skills);
  Sx (sleuth-io) and SkillFortify are adjacent tools with their own locks.
- **Name collision is real:** `skills-lock.json` is used by Vercel's project lock (schemas
  v1/v3 per #542), SkillFortify, and HappySkills. Spec/Show HN text must disambiguate.
- Reddit post (r/clawdbot, 2.6k views / 3 shares) is Karl's; **no crossposting** (his rule).
- Show HN: still unposted as of 10-06; draft refreshed to draft-04 and handed to Karl.
- Benchmark re-run scheduled 03:00 via cron `1afa12ae96a9` (no_agent, script-only, delivers
  to bot-chat). First run's numbers (possibly skewed by concurrent bot experiments):
  e2b 93.6 t/s, e4b 54.8, qwen3-coder:30b 36.0, gemma4:26b-agentic 31.9, 12b 26.4.
- Watches now deliver to bot-chat (was: local, invisible).

## Hardware / ops gotchas (geekom)
- AMD Phoenix1 iGPU, 26GB shared RAM. Never have two 18GB models loaded: Ollama OOMs.
  Use keep_alive=0 when switching benchmarks.
- Ollama serves num_ctx from the Modelfile, not the GGUF's advertised window. Anything
  agent-shaped needs a derived model with `PARAMETER num_ctx >= 65536`.
- Cron jobs do not resolve model aliases: pin raw model + provider + base_url.
