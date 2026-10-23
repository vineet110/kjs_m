import createIntlMiddleware from 'next-intl/middleware';
import { NextResponse, type NextRequest } from 'next/server';

// English only at launch (backlog D2). Add 'hi', 'ar', … here + a messages file later.
const intl = createIntlMiddleware({
  locales: ['en'],
  defaultLocale: 'en',
  localePrefix: 'never',
});

const SESSION_COOKIE = 'kjs_session';

export default function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isPortal = pathname.startsWith('/admin') || pathname.startsWith('/employee');
  const isLogin = pathname === '/employee/login';

  // Only a quick "is there a cookie?" check. FastAPI decides who is really logged in
  // and what they may do; pages call /api/v1/auth/me and redirect on 401.
  if (isPortal && !isLogin && !req.cookies.get(SESSION_COOKIE)) {
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
