"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import { CheckCircle, XCircle, ExternalLink, RefreshCw, Building2 } from "lucide-react";
import { toast } from "sonner";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface PharmaCompany {
  id: string;
  name: string;
  contact_email: string;
  website: string | null;
  description: string | null;
  verified: boolean;
  stripe_account_id: string | null;
  stripe_charges_enabled: boolean;
  stripe_payouts_enabled: boolean;
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

export default function AdminPharmaPage() {
  const { data: session } = useSession();
  const qc = useQueryClient();
  const token = (session as any)?.accessToken as string | undefined;

  const applications = useQuery<PharmaCompany[]>({
    queryKey: ["pharma-applications"],
    queryFn: () => fetchJson(`${API}/api/pharma/applications`, token!),
    enabled: !!token,
  });

  const verified = useQuery<PharmaCompany[]>({
    queryKey: ["pharma-verified"],
    queryFn: () => fetchJson(`${API}/api/pharma/`, token!),
    enabled: !!token,
  });

  const verifyMutation = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      fetchJson(`${API}/api/pharma/verify/${id}`, token!, {
        method: "POST",
        body: JSON.stringify({ approved }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pharma-applications"] });
      qc.invalidateQueries({ queryKey: ["pharma-verified"] });
      toast.success("Company status updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const onboardMutation = useMutation({
    mutationFn: (id: string) =>
      fetchJson<{ url: string }>(`${API}/api/stripe/connect/onboard/${id}`, token!, {
        method: "POST",
      }),
    onSuccess: ({ url }) => {
      window.open(url, "_blank", "noopener,noreferrer");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const refreshStatusMutation = useMutation({
    mutationFn: (id: string) =>
      fetchJson(`${API}/api/stripe/connect/status/${id}`, token!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pharma-verified"] });
      toast.success("Stripe status refreshed");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!token) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Sign in as admin to manage pharma companies.
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <div className="flex items-center gap-3 mb-8">
        <Building2 className="h-7 w-7 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Pharma Management</h1>
          <p className="text-muted-foreground text-sm">Verify applications and manage Stripe Connect accounts</p>
        </div>
      </div>

      <Tabs defaultValue="applications">
        <TabsList className="mb-6">
          <TabsTrigger value="applications">
            Pending Applications
            {applications.data && applications.data.length > 0 && (
              <span className="ml-2 rounded-full bg-red-100 text-red-700 text-xs px-2 py-0.5">
                {applications.data.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="verified">Verified Companies</TabsTrigger>
        </TabsList>

        <TabsContent value="applications">
          <Card>
            <CardHeader>
              <CardTitle>Pending Applications</CardTitle>
              <CardDescription>Review and approve or reject pharma onboarding requests.</CardDescription>
            </CardHeader>
            <CardContent>
              {applications.isLoading ? (
                <p className="text-muted-foreground text-sm">Loading…</p>
              ) : applications.data?.length === 0 ? (
                <p className="text-muted-foreground text-sm">No pending applications.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Company</TableHead>
                      <TableHead>Contact</TableHead>
                      <TableHead>Website</TableHead>
                      <TableHead>Applied</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {applications.data?.map((co) => (
                      <TableRow key={co.id}>
                        <TableCell className="font-medium">{co.name}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{co.contact_email}</TableCell>
                        <TableCell>
                          {co.website ? (
                            <a
                              href={co.website}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 text-primary text-sm hover:underline"
                            >
                              Visit <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : (
                            <span className="text-muted-foreground text-sm">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(co.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex gap-2 justify-end">
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button size="sm" variant="outline" className="text-green-700 border-green-300 hover:bg-green-50">
                                  <CheckCircle className="h-4 w-4 mr-1" /> Approve
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Approve {co.name}?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    This will verify the company and send them an onboarding email.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction onClick={() => verifyMutation.mutate({ id: co.id, approved: true })}>
                                    Approve
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>

                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button size="sm" variant="outline" className="text-red-700 border-red-300 hover:bg-red-50">
                                  <XCircle className="h-4 w-4 mr-1" /> Reject
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Reject {co.name}?</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    This will mark the application as rejected. The company will not be listed.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                                  <AlertDialogAction
                                    className="bg-red-600 hover:bg-red-700"
                                    onClick={() => verifyMutation.mutate({ id: co.id, approved: false })}
                                  >
                                    Reject
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="verified">
          <Card>
            <CardHeader>
              <CardTitle>Verified Companies</CardTitle>
              <CardDescription>Manage Stripe Connect onboarding and payout capabilities.</CardDescription>
            </CardHeader>
            <CardContent>
              {verified.isLoading ? (
                <p className="text-muted-foreground text-sm">Loading…</p>
              ) : verified.data?.length === 0 ? (
                <p className="text-muted-foreground text-sm">No verified companies yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Company</TableHead>
                      <TableHead>Contact</TableHead>
                      <TableHead>Stripe Connect</TableHead>
                      <TableHead>Charges</TableHead>
                      <TableHead>Payouts</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {verified.data?.map((co) => (
                      <TableRow key={co.id}>
                        <TableCell className="font-medium">{co.name}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{co.contact_email}</TableCell>
                        <TableCell>
                          {co.stripe_account_id ? (
                            <Badge variant="outline" className="text-xs font-mono">
                              {co.stripe_account_id.slice(0, 16)}…
                            </Badge>
                          ) : (
                            <Badge variant="secondary">Not connected</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <StripeCapabilityBadge enabled={co.stripe_charges_enabled} />
                        </TableCell>
                        <TableCell>
                          <StripeCapabilityBadge enabled={co.stripe_payouts_enabled} />
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex gap-2 justify-end">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => onboardMutation.mutate(co.id)}
                              disabled={onboardMutation.isPending}
                            >
                              <ExternalLink className="h-3 w-3 mr-1" />
                              {co.stripe_account_id ? "Re-onboard" : "Onboard"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => refreshStatusMutation.mutate(co.id)}
                              disabled={refreshStatusMutation.isPending}
                            >
                              <RefreshCw className="h-3 w-3" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StripeCapabilityBadge({ enabled }: { enabled: boolean }) {
  return enabled ? (
    <Badge className="bg-green-100 text-green-800 border-green-200 text-xs">Enabled</Badge>
  ) : (
    <Badge variant="secondary" className="text-xs">Disabled</Badge>
  );
}
