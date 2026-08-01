"use client";

import { useEffect, useState } from "react";
import { GitCommitHorizontal } from "lucide-react";

type Commit = {
  sha: string;
  message: string;
  date: string;
  url: string;
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function CommitStrip() {
  const [commits, setCommits] = useState<Commit[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/commits")
      .then((res) => {
        if (!res.ok) throw new Error(`commits API ${res.status}`);
        return res.json();
      })
      .then((data: { commits: Commit[] }) => {
        if (cancelled) return;
        if (!data.commits || data.commits.length === 0) {
          setFailed(true);
          return;
        }
        setCommits(data.commits);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Per spec: no fallback text, no hardcoded commit messages — just render
  // nothing (including the label) if the feed can't be fetched.
  if (failed) return null;

  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-muted mb-2">
        Recent activity
      </p>
      <div className="border border-white/10 divide-y divide-white/10">
        {(commits ?? Array.from({ length: 4 })).map((c, i) => (
          <a
            key={c?.sha ?? i}
            href={c?.url ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-white/[0.03] transition-colors"
          >
            <GitCommitHorizontal size={14} className="text-neutral-muted shrink-0" />
            {c ? (
              <>
                <span className="text-neutral-body truncate flex-1">{c.message}</span>
                <span className="font-mono text-[10px] text-neutral-muted shrink-0">
                  {formatDate(c.date)}
                </span>
                <span className="font-mono text-[10px] text-neutral-muted shrink-0">{c.sha}</span>
              </>
            ) : (
              <span className="h-4 flex-1 animate-pulse bg-white/5 rounded-sm" />
            )}
          </a>
        ))}
      </div>
    </div>
  );
}
