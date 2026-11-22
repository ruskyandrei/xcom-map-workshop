### Worktrees and branches are removed when their work is merged

[AGENTS.md](../../AGENTS.md) gains a rule: the turn that merges a branch into main removes its worktree and deletes
the branch (`git branch -d`, which refuses an unmerged one), the worktrees subagents make under `.claude/worktrees`
included; one stays only while its work is not merged or when the user asks to keep it.

The rule follows a clean-up of what the refactor, the follow-ups and the custom geometry work left: 69 worktrees
and 158 local branches, every one already in main. Each worktree's commit was checked to be an ancestor of main
before it went; the only files not committed in them were nine resume checkpoints of finished agents.

Checked: `git worktree list` and `git branch` show the main checkout and `main` alone; the `repo` suite.
