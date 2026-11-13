import createIntlMiddleware from 'next-intl/middleware';
import { NextResponse, type NextRequest } from 'next/server';

// English only at launch (backlog D2). Add 'hi', 'ar', … here + a messages file later.
const intl = createIntlMiddleware({
  locales: ['en'],
  defaultLocale: 'en',
  localePrefix: 'never',
});

const SESSION_COOKIE = 'kjs_session';
// Portal pages that open WITHOUT a login. Exact addresses only: a "starts with" check would also let
// through any page whose address happens to begin the same way.
const NO_LOGIN_PAGES = new Set(['/employee/login', '/employee/forgot-password']);

// Next 16 renamed "middleware" to "proxy" (same job: runs before every page request).
export default function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isPortal = pathname.startsWith('/admin') || pathname.startsWith('/employee');
  const noLogin = NO_LOGIN_PAGES.has(pathname);

  // Only a quick "is there a cookie?" check. FastAPI decides who is really logged in
  // and what they may do; pages call /api/v1/auth/me and redirect on 401.
  if (isPortal && !noLogin && !req.cookies.get(SESSION_COOKIE)) {
    const url = req.nextUrl.clone();
    url.pathname = '/employee/login';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }
  return intl(req);
}

export const config = {
  // Everything except API calls, Next internals and files with an extension (images, videos…)
  matcher: ['/((?!api|_next|.*\\..*).*)'],
};
