import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Must match SESSION_COOKIE in backend/app/config.py.
const SESSION_COOKIE = "medguard_session";

/**
 * Optimistic check only: send visitors without a session cookie to /login before
 * the page loads. The API still verifies the session on every request, and pages
 * redirect to /login themselves if the cookie turns out to be expired.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();

  const login = new URL("/login", request.url);
  login.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/routines/:path*", "/account/:path*"],
};
