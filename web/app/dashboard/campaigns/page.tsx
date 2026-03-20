"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { PlusCircle, Share2, Zap, XCircle, Megaphone } from "lucide-react";
import { toast } from "sonner";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type CampaignStatus = "draft" | "active" | "closed" | "complete";

interface Campaign {
  id: string;
  slug: string;
  title: string;
  story: string;
  goal_usd: number;
  raised_usd: number;
  status: CampaignStatus;
  pharma_id: string | null;
  created_at: string;
}

async function fetchJson<T>(url: string, token: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

async function fetchPublic<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error("Not found");
  return res.json();
}

const createSchema = z.object({
  title: z.string().min(5, "Title must be at least 5 characters"),
  slug: z
    .string()
    .min(3)
    .regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers, and hyphens only"),
  story: z.string().min(20, "Please write at least 20 characters"),
  goal_usd: z.coerce.number().min(100, "Minimum goal is $100"),
});

type CreateForm = z.infer<typeof createSchema>;

function statusBadge(status: CampaignStatus) {
  const map: Record<CampaignStatus, { label: string; className: string }> = {
    draft: { label: "Draft", className: "bg-yellow-100 text-yellow-800 border-yellow-200" },
    active: { label: "Active", className: "bg-green-100 text-green-800 border-green-200" },
    closed: { label: "Closed", className: "bg-gray-100 text-gray-700 border-gray-200" },
    complete: { label: "Complete", className: "bg-blue-100 text-blue-800 border-blue-200" },
  };
  const { label, className } = map[status];
  return <Badge className={`text-xs ${className}`}>{label}</Badge>;
}

function raisedPercent(raised: number, goal: number) {
  return Math.min(100, goal > 0 ? Math.round((raised / goal) * 100) : 0);
}

function ShareButton({ slug }: { slug: string }) {
  const url = `${window.location.origin}/crowdfund/${slug}`;
  return (
    <Button
      size="sm"
      variant="outline"
      onClick={() => {
        navigator.clipboard.writeText(url);
        toast.success("Link copied!");
      }}
    >
      <Share2 className="h-3 w-3 mr-1" /> Share
    </Button>
  );
}

export default function DashboardCampaignsPage() {
  const { data: session } = useSession();
  const qc = useQueryClient();
  const token = (session as any)?.accessToken as string | undefined;
  const [createOpen, setCreateOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateForm>({ resolver: zodResolver(createSchema) });

  // We fetch campaigns by listing the ones the user owns.
  // The API returns all campaigns for the authed user via GET /api/crowdfund/?mine=true
  const campaigns = useQuery<Campaign[]>({
    queryKey: ["my-campaigns"],
    queryFn: () => fetchJson(`${API}/api/crowdfund/?mine=true`, token!),
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateForm) =>
      fetchJson<Campaign>(`${API}/api/crowdfund/`, token!, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-campaigns"] });
      toast.success("Campaign created!");
      setCreateOpen(false);
      reset();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const activateMutation = useMutation({
    mutationFn: (slug: string) =>
      fetchJson(`${API}/api/crowdfund/${slug}/activate`, token!, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-campaigns"] });
      toast.success("Campaign is now live!");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const closeMutation = useMutation({
    mutationFn: (slug: string) =>
      fetchJson(`${API}/api/crowdfund/${slug}/close`, token!, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-campaigns"] });
      toast.success("Campaign closed.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!token) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Sign in to manage campaigns.
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Megaphone className="h-7 w-7 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">My Campaigns</h1>
            <p className="text-muted-foreground text-sm">Create and manage your crowdfunding campaigns</p>
          </div>
        </div>

        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <PlusCircle className="h-4 w-4 mr-2" /> New Campaign
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Create Campaign</DialogTitle>
            </DialogHeader>
            <form
              onSubmit={handleSubmit((d) => createMutation.mutate(d))}
              className="space-y-4 pt-2"
            >
              <div className="space-y-1">
                <Label htmlFor="title">Title</Label>
                <Input id="title" {...register("title")} placeholder="My treatment fund" />
                {errors.title && <p className="text-red-500 text-xs">{errors.title.message}</p>}
              </div>

              <div className="space-y-1">
                <Label htmlFor="slug">URL slug</Label>
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-sm">/crowdfund/</span>
                  <Input id="slug" {...register("slug")} placeholder="my-treatment-fund" className="flex-1" />
                </div>
                {errors.slug && <p className="text-red-500 text-xs">{errors.slug.message}</p>}
              </div>

              <div className="space-y-1">
                <Label htmlFor="goal_usd">Goal (USD)</Label>
                <Input
                  id="goal_usd"
                  type="number"
                  min={100}
                  step={100}
                  {...register("goal_usd")}
                  placeholder="10000"
                />
                {errors.goal_usd && <p className="text-red-500 text-xs">{errors.goal_usd.message}</p>}
              </div>

              <div className="space-y-1">
                <Label htmlFor="story">Your story</Label>
                <Textarea
                  id="story"
                  {...register("story")}
                  rows={4}
                  placeholder="Share your journey and why this treatment matters to you…"
                />
                {errors.story && <p className="text-red-500 text-xs">{errors.story.message}</p>}
              </div>

              <DialogFooter className="pt-2">
                <DialogClose asChild>
                  <Button type="button" variant="outline">Cancel</Button>
                </DialogClose>
                <Button type="submit" disabled={isSubmitting || createMutation.isPending}>
                  {createMutation.isPending ? "Creating…" : "Create Campaign"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {campaigns.isLoading ? (
        <p className="text-muted-foreground text-sm">Loading campaigns…</p>
      ) : campaigns.data?.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-4">
            <Megaphone className="h-12 w-12 text-muted-foreground opacity-40" />
            <p className="text-muted-foreground">You haven&apos;t created any campaigns yet.</p>
            <Button onClick={() => setCreateOpen(true)}>
              <PlusCircle className="h-4 w-4 mr-2" /> Create your first campaign
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {campaigns.data?.map((c) => (
            <CampaignCard
              key={c.id}
              campaign={c}
              onActivate={() => activateMutation.mutate(c.slug)}
              onClose={() => closeMutation.mutate(c.slug)}
              activating={activateMutation.isPending}
              closing={closeMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function CampaignCard({
  campaign: c,
  onActivate,
  onClose,
  activating,
  closing,
}: {
  campaign: Campaign;
  onActivate: () => void;
  onClose: () => void;
  activating: boolean;
  closing: boolean;
}) {
  const pct = raisedPercent(c.raised_usd, c.goal_usd);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle className="text-lg">{c.title}</CardTitle>
            <CardDescription className="mt-1 text-xs font-mono">/crowdfund/{c.slug}</CardDescription>
          </div>
          {statusBadge(c.status)}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground line-clamp-2">{c.story}</p>

        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium">${c.raised_usd.toLocaleString()} raised</span>
            <span className="text-muted-foreground">of ${c.goal_usd.toLocaleString()} goal</span>
          </div>
          <Progress value={pct} className="h-2" />
          <p className="text-xs text-muted-foreground mt-1">{pct}% funded</p>
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          {c.status === "draft" && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button size="sm" disabled={activating}>
                  <Zap className="h-3 w-3 mr-1" /> Publish
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Publish campaign?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Once published, your campaign will be publicly visible and can accept donations.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={onActivate}>Publish</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}

          {c.status === "active" && (
            <>
              <ShareButton slug={c.slug} />
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button size="sm" variant="outline" className="text-red-700 border-red-300" disabled={closing}>
                    <XCircle className="h-3 w-3 mr-1" /> Close
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Close campaign?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will stop accepting donations. This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={onClose}>
                      Close campaign
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          )}

          {(c.status === "closed" || c.status === "complete") && (
            <ShareButton slug={c.slug} />
          )}

          <Button size="sm" variant="ghost" asChild>
            <a href={`/crowdfund/${c.slug}`} target="_blank" rel="noopener noreferrer">
              View page
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
