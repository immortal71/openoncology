import { PUBLIC_ENV_NAMES } from "@/lib/runtime-config";

// Serves the deployment's public settings as JavaScript, read from the server's
// environment on every request. The root layout loads it as a blocking script,
// so `window.__OO_ENV__` exists before any client component runs.
//
// force-dynamic and no-store together are the whole point. Statically rendered
// or cached, this would answer with the values held when the image was built,
// which is the failure it exists to fix.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export function GET() {
  const env: Record<string, string> = {};
  for (const name of PUBLIC_ENV_NAMES) {
    const value = process.env[name];
    // Absent and empty are not the same as "". An empty entry would win over
    // the compiled-in fallback in publicEnv() and silently blank the setting.
    if (value) env[name] = value;
  }

  // JSON.stringify, not string concatenation. These values come from a
  // ConfigMap rather than from a user, but this file is executed as script in
  // every visitor's browser and interpolating into it unescaped is how that
  // stops being true.
  const body = "window.__OO_ENV__=" + JSON.stringify(env) + ";";

  return new Response(body, {
    headers: {
      "content-type": "application/javascript; charset=utf-8",
      "cache-control": "no-store, must-revalidate",
    },
  });
}
