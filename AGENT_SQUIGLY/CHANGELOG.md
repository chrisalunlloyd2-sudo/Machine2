# Changelog

All notable changes to this project.

## 2026-08
- **[Fixed]** fix: the deadline covered the cheap half of the job ($hash)
- **[Fixed]** fix: incremental hashing and a deadline, so a census fits a cell budget ($hash)
- **[Added]** feat: tape join, PowerShell/batch linking, and one unified refresh ($hash)
- **[Added]** feat: agent-squigly — the census that makes the disk visible ($hash)

## 2026-09-29
- **[Test]** states.py: added a `__main__` selftest, matching census and deps. Pure logic, no disk
  or DB. Covers: move resolves before loss+create; modified on same path; genuine loss; genuine
  creation; a reorganisation never reported LOST; summarise counts; identical censuses yield
  zero transitions. Run: `python -m squigly.states`

