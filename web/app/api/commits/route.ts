import { NextResponse } from "next/server";

const REPO = "immortal71/openoncology";

type GitHubCommit = {
  sha: string;
  html_url: string;
  commit: { message: string; author: { date: string } };
};

export async function GET() {
  const res = await fetch(`https://api.github.com/repos/${REPO}/commits?per_page=4`, {
    headers: { Accept: "application/vnd.github+json" },
    next: { revalidate: 86400 },
  });

  if (!res.ok) {
    return NextResponse.json({ commits: [] }, { status: 200 });
  }

  const data: GitHubCommit[] = await res.json();
  const commits = data.map((c) => ({
    sha: c.sha.slice(0, 7),
    message: c.commit.message.split("\n")[0],
    date: c.commit.author.date,
    url: c.html_url,
  }));

  return NextResponse.json({ commits });
}
