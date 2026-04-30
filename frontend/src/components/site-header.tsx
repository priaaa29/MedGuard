"use client";

import { CircleUserRound, Plus, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function SiteHeader() {
  const auth = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/75">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4 md:px-6">
        <Link
          href={auth.status === "authenticated" ? "/routines" : "/"}
          className="-ml-2 flex items-center gap-2 rounded-md px-2 py-2 font-semibold tracking-tight focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <ShieldCheck className="size-5 text-primary" aria-hidden />
          MedGuard
        </Link>

        <nav aria-label="Main" className="flex items-center gap-2">
          {auth.status === "loading" && (
            // Same footprint as the logged-in nav, so nothing jumps when it resolves.
            <div className="flex items-center gap-2" aria-hidden>
              <Skeleton className="h-10 w-28 rounded-lg" />
              <Skeleton className="size-10 rounded-lg" />
            </div>
          )}

          {auth.status === "anonymous" && (
            <>
              <Button asChild variant="ghost">
                <Link href="/login">Log in</Link>
              </Button>
              <Button asChild>
                <Link href="/signup">Sign up</Link>
              </Button>
            </>
          )}

          {auth.status === "authenticated" && (
            <>
              <Button asChild variant="ghost" className="hidden sm:inline-flex">
                <Link href="/routines">My routines</Link>
              </Button>
              <Button asChild>
                <Link href="/routines/new">
                  <Plus data-icon="inline-start" aria-hidden />
                  New routine
                </Link>
              </Button>
              <Button asChild variant="ghost" size="icon">
                <Link href="/account" aria-label={`Account (${auth.user.email})`}>
                  <CircleUserRound className="size-5" aria-hidden />
                </Link>
              </Button>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}
