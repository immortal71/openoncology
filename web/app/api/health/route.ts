import { NextResponse } from "next/server";

// The liveness and readiness probes in infra/helm/templates/web.yaml request
// this path. It did not exist, so every probe took a 404, liveness killed the
// container on its third failure and readiness never let the Service route to
// it: the web tier could not come up in Kubernetes at all, and the chart
// rendered and linted clean the whole time.
//
// Deliberately shallow. Next.js serving a response IS the liveness question,
// and the web tier has no dependency of its own to round-trip — it reaches the
// API from the browser, not from this process. A probe that checked the API
// would take the web pods down whenever the API was down, which is the failure
// mode probes are supposed to prevent rather than spread.
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({ status: "ok", service: "openoncology-web" });
}
