import Link from "next/link";

export default function NotFound() {
  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center px-6">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-2">404</h1>
        <p className="text-slate-600 dark:text-slate-300 mb-6">Page not found</p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-md font-semibold transition-colors"
        >
          Back to home
        </Link>
      </div>
    </main>
  );
}
