# Freight Management System - Agent Workflow Rules

## 1. Autonomous Task Execution
- When assigned a task or user request, autonomously execute all necessary development steps to achieve the goal end-to-end.
- This includes reading/writing files, creating new components, running database module upgrades, and running test suites without asking repetitive permissions for standard implementation steps.

## 2. Git Operations Boundary (Strictly No Modifying Git Commands)
- **NEVER** run git-modifying commands:
  - Do not run `git add`
  - Do not run `git commit`
  - Do not run `git push`
  - Do not run `git reset`, `git checkout .`, `git rebase`, or `git merge`
- All git commits, staging, and remote pushes are handled exclusively by the user.
- Read-only commands (e.g. `git status`, `git diff`, `git log`) are allowed when needed for situational context.
