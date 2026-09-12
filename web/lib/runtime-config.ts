/**
 * Public configuration read at request time rather than baked into the bundle.
 *
 * `NEXT_PUBLIC_*` is a compile-time substitution. Next replaces every literal
 * `process.env.NEXT_PUBLIC_X` in client code with the value present when
 * `next build` ran, and nothing can change it afterwards. Both deployment paths
 * supplied these at runtime instead: docker-compose sets them under
 * `environment:`, and the Helm ConfigMap sets them from the ingress hostnames.
 * Neither reaches a bundle that was compiled during `docker build`, where no
 * such variable exists.
 *
 * What shipped was an image with `http://localhost:8000` compiled in as the API
 * address and `undefined` as the Keycloak one — so the deployed site called an
 * API on the visitor's own machine, and `login()` threw "Keycloak is not
 * configured in this environment" for everybody.
 *
 * The alternative is build args, which works and produces an image that is only
 * valid for the hostnames it was built for. One image published per commit and
 * promoted from staging to production is worth more than that, so the values
 * are served instead: `app/env.js/route.ts` renders the server's environment
 * into `window.__OO_ENV__`, and the root layout loads it as a blocking script
 * before hydration.
 */

export type PublicEnvName =
  | "NEXT_PUBLIC_API_URL"
  | "NEXT_PUBLIC_KEYCLOAK_URL"
  | "NEXT_PUBLIC_KEYCLOAK_REALM"
  | "NEXT_PUBLIC_KEYCLOAK_CLIENT_ID"
  | "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY"
  | "NEXT_PUBLIC_ENABLE_DEMO_AUTH";

export const PUBLIC_ENV_NAMES: PublicEnvName[] = [
  "NEXT_PUBLIC_API_URL",
  "NEXT_PUBLIC_KEYCLOAK_URL",
  "NEXT_PUBLIC_KEYCLOAK_REALM",
  "NEXT_PUBLIC_KEYCLOAK_CLIENT_ID",
  "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY",
  "NEXT_PUBLIC_ENABLE_DEMO_AUTH",
];

declare global {
  interface Window {
    __OO_ENV__?: Partial<Record<PublicEnvName, string>>;
  }
}

// Each read is a separate literal so Next can substitute it, and the switch is
// evaluated per call rather than once at module scope: a map built at import
// time would freeze whatever the environment held before a test could set it.
function compiledIn(name: PublicEnvName): string | undefined {
  switch (name) {
    case "NEXT_PUBLIC_API_URL":
      return process.env.NEXT_PUBLIC_API_URL;
    case "NEXT_PUBLIC_KEYCLOAK_URL":
      return process.env.NEXT_PUBLIC_KEYCLOAK_URL;
    case "NEXT_PUBLIC_KEYCLOAK_REALM":
      return process.env.NEXT_PUBLIC_KEYCLOAK_REALM;
    case "NEXT_PUBLIC_KEYCLOAK_CLIENT_ID":
      return process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID;
    case "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY":
      return process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;
    case "NEXT_PUBLIC_ENABLE_DEMO_AUTH":
      return process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH;
  }
}

/**
 * The effective value of a public setting.
 *
 * In the browser the injected value wins, because it is the only one that knows
 * where this deployment actually lives. On the server `process.env` is the live
 * environment and is read directly. Both fall back to whatever was compiled in,
 * which is what keeps `next dev` and the Vitest suite working unchanged.
 */
// The fallback below is silent by design in development, where nothing injects
// anything and the defaults are correct. Anywhere else its silence is the
// problem: a /env.js that failed to load looks exactly like a working page
// pointed at the visitor's own machine. This says so once, in the console.
let warned = false;
function warnIfUninjected(): void {
  if (warned || window.__OO_ENV__) return;
  warned = true;
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return;
  console.error(
    "[openoncology] /env.js did not load, so this page is falling back to the " +
      "settings compiled into the bundle — which point at localhost. Check " +
      "that the root layout still loads it and that the server serves it."
  );
}

export function publicEnv(name: PublicEnvName): string | undefined {
  if (typeof window !== "undefined") {
    warnIfUninjected();
    const injected = window.__OO_ENV__?.[name];
    if (injected) return injected;
  } else {
    const live = process.env[name];
    if (live) return live;
  }
  return compiledIn(name) || undefined;
}

/** The same value with a default, for the settings that have a sensible one. */
export function publicEnvOr(name: PublicEnvName, fallback: string): string {
  return publicEnv(name) ?? fallback;
}
