# Context Update Protocol

Load this file when the user asks "should we update context?" or similar.

## When to Update

| Trigger                        | Update target           |
|--------------------------------|-------------------------|
| Task/step changed              | `STATE.md`              |
| Feature shipped or blocked     | `STATE.md` status table |
| Architectural decision made    | `docs/ARCHITECTURE.md`  |
| New convention or tool adopted | `CLAUDE.md`             |
| New key file created           | `STATE.md` key files    |

## Rules

1. **Never update context files without user request** — propose changes, wait
   for approval.
2. **Pointers, not descriptions** — reference `file:lines`, don't copy content.
3. **STATE.md must stay under 80 lines** — archive completed phases to
   `docs/PHASE-N-SUMMARY.md` if needed.
4. **One concern per entry** — keep table rows atomic.

## Good vs Bad Entries

```
# Good (pointer)
D8: Rate limiting via slowapi → docs/demo-architecture.md:84-95

# Bad (duplicated content)
D8: Rate limiting — we use slowapi which wraps limits library and applies
    per-endpoint decorators with Redis backend for distributed counting...
```

## Proposing Changes

When suggesting a context update, use this format:

```
### Proposed Context Update

- [ ] **STATE.md** — Mark Step 1 as DONE, advance "Up Next" to Step 2
- [ ] **ARCHITECTURE.md** — Add D8: rate limiting decision
- [ ] **CLAUDE.md** — No changes needed

Approve? (y/n)
```
