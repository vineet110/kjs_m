# Learning: how we learn in the AI era

> AI can write code faster than us. Our job is to **understand, decide, and verify**: to know what good looks like and to spot when something is wrong. That's what we're training.

## The 5 rules
1. **Never commit code you can't explain.** If you can't explain a line, ask Claude to explain it. If you still can't, don't merge it.
2. **Just in time, not just in case.** Learn the topic the week you need it (see `00-roadmap.md`). Don't binge courses first.
3. **Predict, then run.** Before running code or a test, say out loud what you think will happen. Being wrong is where the learning happens.
4. **Type the first one yourself.** The first endpoint, the first migration, the first component: write it by hand with Claude as a tutor. After that, let Claude draft and you review.
5. **Teach it back.** Explain what you built to your teammate in 2 minutes. If you can't, you don't know it yet.

## The learning loop (per new concept)
```
Meet it in the task  →  Ask Claude: "explain X in 5 lines + a tiny example"
→  Read the official docs page (15 min, linked in the files here)
→  Use it in our code  →  Break it on purpose (what error do you get?)
→  Write 2–3 lines in learning-log.md in your own words
```

## Asking Claude good learning questions
- "Explain ___ like I know Python basics but not web frameworks."
- "What problem does ___ solve? What did people do before it?"
- "Show the smallest possible example, then show how we use it in our repo."
- "What are 3 mistakes beginners make with ___?"
- "Quiz me with 3 questions on what we just built."

## Files here
| File | What |
|---|---|
| `00-roadmap.md` | What to learn each week, mapped to `track.md` |
| `01-foundations.md` | Git, terminal, HTTP, JSON, env vars, Docker |
| `02-backend.md` | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, Postgres, pytest |
| `03-frontend.md` | TypeScript, React, Next.js, Tailwind, shadcn, TanStack Query, forms |
| `04-concepts.md` | The ideas behind this project: auth, roles, audit, queues, idempotency, time, SEO, RAG |
| `05-working-with-claude.md` | Plan mode, reviewing AI code, verifying, prompts |
| `learning-log.md` | Our daily "today I learned" |
