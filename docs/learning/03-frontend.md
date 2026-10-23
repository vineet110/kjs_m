# Frontend: TypeScript, React, Next.js

## The one idea to get right: server vs client components
- **Server components** (default in the App Router) run on the server and send HTML. They're good for SEO and speed. **All our public pages.**
- **Client components** (`"use client"`) run in the browser and handle clicks and state. **Gate modal, configurator, Koko, all portal/admin screens.**
- Public content is fetched on the server and cached with **ISR tags**. When the admin edits a product, FastAPI tells Next.js to revalidate that tag.

| Topic | Learn | Where |
|---|---|---|
| TypeScript | types vs interfaces, unions, generics (just reading them), `strict` mode | typescriptlang.org → Handbook (Basics, Everyday Types) |
| React | components, props, state, effects (and when *not* to use them), lists & keys | react.dev → Learn |
| Next.js App Router | `app/` folders = routes, `layout.tsx`, `page.tsx`, dynamic `[slug]`, `generateMetadata`, `generateStaticParams`, middleware, caching & revalidation | nextjs.org/docs → App Router |
| Tailwind | utility classes, responsive (`md:`), **logical** classes (`ms-`, `me-`) for RTL | tailwindcss.com/docs |
| shadcn/ui | copy-in components (Button, Dialog, Table…) built on Radix | ui.shadcn.com |
| next-intl | locale routing (`/en`), `useTranslations`, messages JSON | next-intl docs |
| TanStack Query | `useQuery`, `useMutation`, cache invalidation | tanstack.com/query → React docs |
| Forms | react-hook-form + zod schemas (mirror the Pydantic rules) | react-hook-form.com · zod.dev |
| Playwright | write an E2E test for a user journey | playwright.dev → Getting started |
| Accessibility | labels, focus, keyboard, colour + text for status | developer.mozilla.org → Accessibility |

## First exercises (Phase 1)
1. By hand: a `/[locale]/page.tsx` server component that prints a translated "Hello KJS".
2. A shared `Sidebar` that reads menu items from one config and filters them by role.
3. Middleware that redirects `/portal/*` to `/employee/login` when there's no session cookie.
4. Generate the API client from FastAPI's OpenAPI and call `/api/auth/me` with TanStack Query.
