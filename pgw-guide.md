# Parallel Git Worktree Guide

Quick reference for the `pgw` helper script.

## Create a New Worktree

```bash
./pgw <branch-name>
```

Examples:
```bash
./pgw config-menu-refactor
./pgw beacon-integration
./pgw led-debug-features
```

This creates an isolated worktree at `/mnt/d/github-projects/.worktrees/<branch>` and opens it in Cursor.

## List All Worktrees

```bash
git worktree list
```

## Merge a Branch Back to Main

```bash
# 1. Go to main repo
cd /mnt/d/github-projects/gschpoozi

# 2. Ensure main is current
git checkout main
git pull  # if using remote

# 3. Merge the branch
git merge <branch-name>

# 4. Remove the worktree
git worktree remove /mnt/d/github-projects/.worktrees/<branch-name>

# 5. Delete the branch (optional)
git branch -d <branch-name>
```

## Handle Merge Conflicts

```bash
# After merge shows conflicts:
# 1. Edit files to resolve conflicts
# 2. Stage resolved files
git add .

# 3. Complete the merge
git commit
```

## Force Remove a Worktree

If a worktree has uncommitted changes you want to discard:

```bash
git worktree remove --force /mnt/d/github-projects/.worktrees/<branch-name>
```

## Prune Stale Worktrees

If you manually deleted a worktree directory:

```bash
git worktree prune
```
