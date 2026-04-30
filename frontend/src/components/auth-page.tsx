import { Suspense } from "react";
import type { ReactNode } from "react";
import { AuthForm } from "@/components/auth-form";
import { Skeleton } from "@/components/ui/skeleton";

function FormSkeleton() {
  return (
    <div className="space-y-6" aria-hidden>
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-11 w-full" />
    </div>
  );
}

export function AuthPage({ mode, title, intro }: { mode: "login" | "signup"; title: string; intro: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-sm px-4 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-muted-foreground">{intro}</p>
      <div className="mt-8">
        {/* AuthForm reads ?next=, which is only known at request time. */}
        <Suspense fallback={<FormSkeleton />}>
          <AuthForm mode={mode} />
        </Suspense>
      </div>
    </div>
  );
}
