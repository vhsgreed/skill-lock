# Reply to jimy-r (2026-10-02 22:19Z) -- draft for Karl's sign-off

Positions, one sentence each (for Karl):
1. Harness-visible = workspace root: his probe shows loading follows reads, so "a scanned
   skills directory" is the wrong boundary and the workspace root is the one an installer
   can actually know.
2. Canary test adopted as a SHOULD: put a canary skill in staging, read a file next to it,
   confirm the session roster does not change; it is the first test of harness-visible that
   a tool can run without knowing any harness internals.
3. Spell out the cross-volume case rather than hiding behind "where the filesystem allows
   it": verify outside, copy in under a name that is not a skills folder, hash again, then
   rename; the extra hash is cheap and it is the only step that survives a copy-based move.

---

**@jimy-r** -- both points land, and the probe is the part I care about most, because it
is evidence about how loading actually behaves instead of a claim about configuration.

**Step 1: harness-visible.** You are right that "outside any skills/plugins directory the
harness scans" assumes a harness that scans fixed directories, and your probe shows
loading following the read instead. So draft-04 will define it by the boundary an installer
can actually know: a location is harness-visible if it is inside the workspace root. Outside
the workspace root: not visible. Inside it: assume visible, even in nested folders, even
with innocuous names. That is the conservative reading of your evidence and it does not
depend on any harness's directory list.

**The canary test is adopted.** Put a canary skill in the staging location, read a file
beside it from a session, and confirm the session roster does not change. That goes in as
a SHOULD for installers, with one line of rationale: it is the only check of harness
visibility that runs without knowing harness internals. Credit to your probe.

**Step 3: cross-volume moves.** Spelled out rather than left to "where the filesystem
allows it", because your case is the common one and a rename-across-volumes is a copy with
a surprise inside it. The normative sequence for the cross-volume case:

1. verify outside the workspace root (staging),
2. copy into the target volume under a name the harness will not treat as a skills folder,
3. hash the copied tree again and compare against the verified tree,
4. only then rename into the load path.

The re-hash after the copy is the step that earns its keep: it is the only check that
tells you the bytes that will load are the bytes that were verified. Atomic rename is
kept where the filesystem offers it; where it does not, steps 2-4 are the required
substitute and the spec will say so instead of quietly downgrading to "best effort".

-- Karl (github.com/vhsgreed)
