/**
 * Keycloak browser-side auth helper.
 * Wraps the Keycloak JS adapter so pages can call auth.init(),
 * read auth.token, and redirect to login / logout.
 *
 * Token is stored in sessionStorage under "kc_token" so that
 * lib/api.ts can read it without importing this module.
 */

export interface KeycloakUser {
  sub: string;
  email: string;
  name: string;
  roles: string[];
}

export type AuthState = {
  authenticated: boolean;
  token: string | null;
  user: KeycloakUser | null;
};

const TOKEN_KEY = "kc_token";
const DEMO_TOKEN = "demo-local-token";
const DEMO_USER: KeycloakUser = {
  sub: "demo-user",
  email: "demo@openoncology.local",
  name: "Local Demo User",
  roles: ["patient"],
};

function isDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  return process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH === "1";
}

// ─── Lazy-loaded Keycloak instance ────────────────────────────────────────────

let _kc: import("keycloak-js").default | null = null;

async function getKeycloak() {
  if (_kc) return _kc;
  const Keycloak = (await import("keycloak-js")).default;
  _kc = new Keycloak({
    url: process.env.NEXT_PUBLIC_KEYCLOAK_URL ?? "http://localhost:8080",
    realm: process.env.NEXT_PUBLIC_KEYCLOAK_REALM ?? "openoncology",
    clientId: process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? "openoncology-web",
  });
  return _kc;
}

// ─── Public helpers ────────────────────────────────────────────────────────────

/** Initialise Keycloak and attempt silent SSO check. Returns auth state. */
export async function initAuth(): Promise<AuthState> {
  if (typeof window === "undefined") {
    return { authenticated: false, token: null, user: null };
  }

  if (isDemoMode()) {
    sessionStorage.setItem(TOKEN_KEY, DEMO_TOKEN);
    return { authenticated: true, token: DEMO_TOKEN, user: DEMO_USER };
  }

  const keycloakUrl = process.env.NEXT_PUBLIC_KEYCLOAK_URL;
  if (!keycloakUrl) {
    return { authenticated: false, token: null, user: null };
  }

  const kc = await getKeycloak();

  let authenticated = false;
  try {
    authenticated = await kc.init({
      onLoad: "check-sso",
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      pkceMethod: "S256",
    });
  } catch {
    sessionStorage.removeItem(TOKEN_KEY);
    return { authenticated: false, token: null, user: null };
  }

  if (authenticated && kc.token) {
    sessionStorage.setItem(TOKEN_KEY, kc.token);

    // Schedule token refresh 60 s before expiry
    kc.onTokenExpired = () => {
      kc.updateToken(60).then((refreshed) => {
        if (refreshed && kc.token) {
          sessionStorage.setItem(TOKEN_KEY, kc.token);
        }
      });
    };

    return { authenticated: true, token: kc.token, user: parseUser(kc) };
  }

  sessionStorage.removeItem(TOKEN_KEY);
  return { authenticated: false, token: null, user: null };
}

/** Redirect browser to Keycloak login page. */
export async function login() {
  if (typeof window === "undefined") return;
  if (isDemoMode()) {
    sessionStorage.setItem(TOKEN_KEY, DEMO_TOKEN);
    return;
  }

  if (!process.env.NEXT_PUBLIC_KEYCLOAK_URL) {
    throw new Error("Keycloak is not configured in this environment.");
  }

  const kc = await getKeycloak();
  await kc.login({ redirectUri: window.location.href });
}

/** Logout and clear token. */
export async function logout() {
  const kc = await getKeycloak();
  sessionStorage.removeItem(TOKEN_KEY);
  await kc.logout({ redirectUri: window.location.origin });
}

/** Returns the current token string or null. */
export function getToken(): string | null {
  return typeof window !== "undefined" ? sessionStorage.getItem(TOKEN_KEY) : null;
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

function parseUser(kc: import("keycloak-js").default): KeycloakUser {
  const parsed = kc.tokenParsed as Record<string, unknown> | undefined;
  const realmRoles =
    (parsed?.realm_access as { roles?: string[] } | undefined)?.roles ?? [];
  return {
    sub: (parsed?.sub as string) ?? "",
    email: (parsed?.email as string) ?? "",
    name: (parsed?.name as string) ?? "",
    roles: realmRoles,
  };
}
