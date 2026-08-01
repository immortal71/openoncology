import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { getToken, initAuth } from "@/lib/auth";

describe("auth.getToken", () => {
  beforeEach(() => sessionStorage.clear());

  it("returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("returns the stored kc_token", () => {
    sessionStorage.setItem("kc_token", "abc");
    expect(getToken()).toBe("abc");
  });
});

describe("auth.initAuth — demo mode", () => {
  const originalEnv = process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH;

  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH = originalEnv;
    vi.restoreAllMocks();
  });

  it("authenticates immediately with the demo user when demo auth is enabled", async () => {
    process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH = "1";
    const state = await initAuth();

    expect(state.authenticated).toBe(true);
    expect(state.token).toBe("demo-local-token");
    expect(state.user?.roles).toContain("patient");
    // Token is persisted so lib/api can read it.
    expect(sessionStorage.getItem("kc_token")).toBe("demo-local-token");
  });

  it("returns unauthenticated when demo auth is off and Keycloak is unconfigured", async () => {
    process.env.NEXT_PUBLIC_ENABLE_DEMO_AUTH = "0";
    delete process.env.NEXT_PUBLIC_KEYCLOAK_URL;

    const state = await initAuth();
    expect(state.authenticated).toBe(false);
    expect(state.token).toBeNull();
  });
});
