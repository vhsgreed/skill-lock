# AGENTS.md — working agreement for this repo

Multiple Hermes surfaces (bot, desktop, CLI) work on this project. Chat context is
per-surface and goes stale; the repo does not. Rules:

1. **Read first:** `STATUS.md` and `git log --oneline -10` before any work. A session's
   memory of "where we are" is stale by definition — the log is the only truth.
2. **Write last:** update `STATUS.md` in the same commit as any work that changes state
   (spec version, tests, open decisions, thread ownership).
3. **One poster per thread:** `STATUS.md` records which surface owns which external thread.
   Do not post to a thread you do not own without saying so there first.
4. **Spec claims need commits.** Never announce a spec change in a thread before the
   commit is pushed.
5. **External text: zero em dashes** (Karl's rule). English, literal names over coined ones.
6. **TDD is enforced** (tests/test-driven-development behavior): failing test first,
   corpus bands hold (malicious must flag, benign must be silent, needs-review must flag).
7. Spec commitments that bind the project (governance home, licensing, standard donation)
   are Karl's decisions alone. Draft them, recommend, wait.
