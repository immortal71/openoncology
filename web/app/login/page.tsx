"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/components/providers/AuthProvider";

function LoginContent() {
  const { auth, login, isLoading } = useAuth();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/dashboard";

  useEffect(() => {
    if (auth.authenticated && typeof window !== "undefined") {
      window.location.href = next;
    }
  }, [auth.authenticated, next]);

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Sign in to OpenOncology</h1>
        <p className="text-sm text-gray-600 mb-6">
          Continue with Keycloak for full account access. If Keycloak is unavailable in local testing,
          use direct submit mode.
        </p>

        <Button
          className="w-full"
          onClick={() => login()}
          disabled={isLoading}
        >
          {isLoading ? "Checking session..." : "Continue with Keycloak"}
        </Button>

        <Link
          href="/submit"
          className="mt-3 block w-full text-center border border-gray-200 rounded-md py-2 text-sm text-gray-700 hover:bg-gray-50"
        >
          Continue to Submit (Local Test Mode)
        </Link>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-screen flex items-center justify-center p-6"><p className="text-sm text-slate-500">Loading login...</p></main>}>
      <LoginContent />
    </Suspense>
  );
}