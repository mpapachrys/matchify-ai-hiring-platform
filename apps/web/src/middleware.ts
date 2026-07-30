import { NextResponse, type NextRequest } from "next/server";

/**
 * Route guard and silent session renewal.
 *
 * NOTE ON LOCATION: this file must live in `src/`, not the project root, because
 * the app uses a `src/` directory. Next.js silently ignores a root-level
 * middleware.ts in that layout — no warning, no build entry, it just never runs.
 *
 * Two jobs:
 *
 * 1. **Renew expired access tokens.** Access tokens last 15 minutes; refresh
 *    tokens last a week. Middleware is the only place in the App Router that can
 *    both read the request cookies and write new ones onto the response — a
 *    Server Component can do the first but not the second. Without this, a user
 *    who came back after 15 minutes would be signed out on their next
 *    server-rendered navigation even though their refresh token was still valid.
 *
 * 2. **Send people to the right shell.** This is a UX affordance, not a security
 *    boundary: it prevents a flash of the wrong dashboard. A forged `mx_role`
 *    cookie earns a redirect to a page whose every data call is then rejected by
 *    FastAPI, which verifies the signed JWT. Authorization lives in
 *    `apps/api/app/api/deps.py`.
 */

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://api:8000";

const AUTH_ROUTES = ["/login", "/register"];
const ACCESS_COOKIE = "mx_access";
const REFRESH_COOKIE = "mx_refresh";
const ROLE_COOKIE = "mx_role";
const SESSION_COOKIES = [ACCESS_COOKIE, REFRESH_COOKIE, ROLE_COOKIE];

function homeFor(role: string | undefined): string {
  return role === "hiring_manager" ? "/manager/dashboard" : "/candidate/dashboard";
}

function readCookieValue(setCookieHeader: string, name: string): string | undefined {
  if (!setCookieHeader.startsWith(`${name}=`)) return undefined;
  return setCookieHeader.slice(name.length + 1).split(";")[0];
}

export async function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  let role = request.cookies.get(ROLE_COOKIE)?.value;

  let hasSession = Boolean(access);
  let renewed: string[] = [];
  let staleSession = false;

  // The access cookie's lifetime matches the token's, so its absence alongside a
  // surviving refresh cookie is precisely the "came back later" case.
  if (!access && refresh) {
    try {
      const response = await fetch(`${API_INTERNAL_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { cookie: request.headers.get("cookie") ?? "" },
      });

      if (response.ok) {
        hasSession = true;
        renewed = response.headers.getSetCookie();
        role = renewed.map((c) => readCookieValue(c, ROLE_COOKIE)).find(Boolean) ?? role;
      } else {
        // Refresh was rejected (expired, revoked, or replayed). The cookies are
        // dead weight — drop them, or they would bounce this user off /login
        // forever while no page can actually authenticate them.
        staleSession = true;
      }
    } catch {
      // API unreachable — treat as signed out rather than hanging the request.
      staleSession = true;
    }
  }

  // A server-side auth check that failed sends users here. Honour it even if
  // cookies are still present, so a token this middleware cannot validate
  // (a rotated JWT secret, say) can never produce a redirect loop.
  if (searchParams.get("session") === "expired") {
    hasSession = false;
    staleSession = true;
  }

  const finalize = (response: NextResponse): NextResponse => {
    for (const cookie of renewed) response.headers.append("set-cookie", cookie);
    if (staleSession) {
      for (const name of SESSION_COOKIES) response.cookies.delete(name);
    }
    return response;
  };

  /**
   * Continue to the page, forwarding any freshly minted cookies onto the
   * *request* as well as the response.
   *
   * Setting them only on the response is not enough: Server Components read the
   * cookies of the request they were handed, which still carries the expired
   * set. The browser would get a valid token while the render that triggered the
   * refresh still saw none — and bounced the user to /login anyway.
   */
  const proceed = (): NextResponse => {
    if (renewed.length === 0) return finalize(NextResponse.next());

    const jar = new Map(request.cookies.getAll().map((c) => [c.name, c.value]));
    for (const cookie of renewed) {
      const [pair] = cookie.split(";");
      const separator = pair.indexOf("=");
      if (separator > 0) jar.set(pair.slice(0, separator), pair.slice(separator + 1));
    }

    const headers = new Headers(request.headers);
    headers.set(
      "cookie",
      [...jar].map(([name, value]) => `${name}=${value}`).join("; "),
    );

    return finalize(NextResponse.next({ request: { headers } }));
  };

  // Signed-in users have no reason to see the auth screens.
  if (AUTH_ROUTES.includes(pathname) && hasSession) {
    return finalize(NextResponse.redirect(new URL(homeFor(role), request.url)));
  }

  const isProtected = pathname.startsWith("/candidate") || pathname.startsWith("/manager");

  if (isProtected && !hasSession) {
    const login = new URL("/login", request.url);
    if (pathname !== "/candidate/dashboard" && pathname !== "/manager/dashboard") {
      login.searchParams.set("next", pathname);
    }
    return finalize(NextResponse.redirect(login));
  }

  if (pathname.startsWith("/manager") && role === "candidate") {
    return finalize(NextResponse.redirect(new URL("/candidate/dashboard", request.url)));
  }

  if (pathname.startsWith("/candidate") && role === "hiring_manager") {
    return finalize(NextResponse.redirect(new URL("/manager/dashboard", request.url)));
  }

  return proceed();
}

export const config = {
  matcher: ["/candidate/:path*", "/manager/:path*", "/login", "/register"],
};
