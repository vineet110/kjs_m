# Working with Claude (Claude Code)

## The workflow that works
1. **Plan mode first** for any feature: Claude proposes files, tables, endpoints and tests. You read it and ask "why?" until you agree.
2. **Small steps.** One endpoint or one screen per request. Big asks produce big code you can't review.
3. **Review every diff.** Read it like you'll be woken at 2 am to fix it. Ask: what does this do? What if the input is empty? What if the user isn't allowed?
4. **Verify, don't trust.** Run the tests, click the feature, try the forbidden role. Claude can be confidently wrong, and so can we.
5. **Keep context in files, not in chat.** Decisions → `memory.md`. Next steps → `track.md`. New sessions start by reading them.

## Red flags in AI-written code
- New dependencies you didn't ask for
- Tests that only cover the happy path, or that "test" the mock instead of the code
- Catching every exception and ignoring it
- Hard-coded secrets, URLs or IDs
- Logic in the router instead of the service
- Missing role check or missing audit row
- Changing many unrelated files in one go

## When to ask a human (senior friend) instead
- Security-sensitive design (auth, sessions, file uploads) before it ships
- Production data / server access decisions
- When Claude and you go back and forth 3 times without progress
- Anything about client relationships, scope or deadlines

## Useful Claude Code habits
- `CLAUDE.md` at the repo root is read automatically. Keep it short and point to `docs/`.
- Ask for a plan, then say "implement step 1 only".
- Ask "what did you not test?" after a change.
- Use the review prompt in `docs/prompt.md` before opening a PR.
