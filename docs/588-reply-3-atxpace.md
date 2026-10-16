@atxpace Thanks for the disclosure and the concrete ask. Persuaded on Q4, with one reservation.

Conceded: nothing in skills-lock needs SKILL.md to change, and this repo's bar ("when in doubt, leave it out") plus @jonathanhefner's take on #252 (integrity belongs at the distribution layer) point the same way you do. skills-lock stays at vhsgreed/skill-lock, versioned on its own clock. I'm withdrawing the donation plan.

The reservation: npm's lockfiles coexist because each tool owns its install tree. Skill directories are shared across tools and harnesses, so two drift reports on the same tree can disagree today. Appendix A already admits `tree_hash` and `skillFolderHash` can't verify each other because the input sets differ. That gap is an artifact question, which is your point.

So I'll open a separate, narrow proposal here for a normative definition of which files belong to a skill directory. Two questions so it covers your case:

1. Which exclusions does SkillRepo apply when it SHA-matches on publish?
2. Do you hash symlinks as links or follow them?

For Appendix A I'd map your statuses as `edited` = `modified`, `missing` = `missing`. `stale` has no counterpart, since a lockfile knows the pin, not the upstream head. Correct me if that's wrong.

-- Karl (github.com/vhsgreed)
