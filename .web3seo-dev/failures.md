# Failures log

Append-only. Format per entry:

- **Date** (UTC)
- **Symptom** (what did the user / cron / test see?)
- **Root cause** (the actual reason, ideally with commit / log line)
- **Fix** (what was changed)
- **Prevention** (test / guard / process that would catch this earlier)

Focus this log on failure modes that **couldn't have been predicted from reading the code**.
Run-of-the-mill bugs go in commit messages, not here.

---

(empty — append entries as they happen)
