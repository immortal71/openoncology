import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware runs on the Edge runtime — Keycloak JS cannot run here.
 * Strategy: check for the presence of the "kc_token" sessionStorage key
 * by looking at a lightweight cookie "kc_auth" that the AuthProvider sets
 * on the client whenever it successfully authenticates.
 *
 * Protected routes that need authentication:
 *   /dashboard, /submit, /oncologist
 *
 * Protected routes that need the "oncologist" role:
 *   /oncologist
 *
 * Role enforcement is done server-side here by reading the cookie set by
 * the client-side AuthProvider. The real security boundary is the FastAPI
 * backend JWT check — this middleware is only for UX redirection.
 */

const PROTECTED = ["/dashboard", "/submit", "/oncologist"];
const ONCOLOGIST_ONLY = ["/oncologist"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED.some((path) => pathname.startsWith(path));
  if (!isProtected) return NextResponse.next();

  // Client sets "kc_auth=1" cookie after successful auth, "kc_role=oncologist" when applicable
  const isAuthed = request.cookies.get("kc_auth")?.value === "1";
  if (!isAuthed) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const isOncologistRoute = ONCOLOGIST_ONLY.some((path) => pathname.startsWith(path));
  if (isOncologistRoute) {
    const role = request.cookies.get("kc_role")?.value ?? "";
    if (!role.includes("oncologist")) {
      const denied = request.nextUrl.clone();
      denied.pathname = "/";
      return NextResponse.redirect(denied);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/submit/:path*", "/oncologist/:path*"],
};
