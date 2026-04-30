"use client";

import { Loader2, LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { toast } from "sonner";
import { useAuth } from "@/components/auth-provider";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useApiQuery } from "@/lib/use-api";

export function AccountView() {
  const router = useRouter();
  const auth = useAuth();
  const query = useApiQuery(api.me, "/account");
  const [loggingOut, setLoggingOut] = useState(false);

  async function logout() {
    setLoggingOut(true);
    await auth.logout();
    router.replace("/");
  }

  return (
    <div className="space-y-10">
      <section aria-labelledby="profile-heading" className="rounded-xl border border-border bg-card p-6">
        <h2 id="profile-heading" className="sr-only">
          Profile
        </h2>
        {query.status === "success" ? (
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm text-muted-foreground">Email</dt>
              <dd className="mt-1 font-medium break-all">{query.data.email}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">Member since</dt>
              <dd className="mt-1 font-medium">{formatDate(query.data.created_at)}</dd>
            </div>
          </dl>
        ) : query.status === "error" ? (
          <div role="alert" className="flex flex-col items-start gap-3">
            <p className="text-muted-foreground">{query.error.message}</p>
            <Button variant="outline" onClick={query.reload}>
              Try again
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2" aria-busy>
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        )}
        <Button variant="outline" className="mt-6" onClick={logout} disabled={loggingOut}>
          {loggingOut ? (
            <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden />
          ) : (
            <LogOut data-icon="inline-start" aria-hidden />
          )}
          Log out
        </Button>
      </section>

      <section aria-labelledby="delete-heading" className="rounded-xl border border-destructive/30 p-6">
        <h2 id="delete-heading" className="font-semibold">
          Delete account
        </h2>
        <p className="mt-1 max-w-prose text-muted-foreground">
          Permanently deletes your account and every saved routine. This can&apos;t be undone.
        </p>
        <DeleteAccountDialog />
      </section>
    </div>
  );
}

function DeleteAccountDialog() {
  const router = useRouter();
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!password) return setError("Enter your password to confirm.");
    setDeleting(true);
    try {
      await api.deleteAccount(password);
      auth.setUser(null);
      toast.success("Your account and routines have been deleted.");
      router.replace("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't delete your account. Please try again.");
      setDeleting(false);
    }
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setPassword("");
          setError(null);
        }
      }}
    >
      <AlertDialogTrigger asChild>
        <Button variant="destructive" className="mt-4">
          Delete my account
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <form onSubmit={submit} noValidate className="space-y-4">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete your account?</AlertDialogTitle>
            <AlertDialogDescription>
              All your routines will be deleted with it. Enter your password to confirm.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor="confirm-password">Password</FieldLabel>
            <Input
              id="confirm-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "confirm-password-error" : undefined}
            />
            {error && <FieldError id="confirm-password-error">{error}</FieldError>}
          </Field>
          <AlertDialogFooter>
            <AlertDialogCancel type="button">Cancel</AlertDialogCancel>
            {/* A plain submit button, not AlertDialogAction, so the dialog stays open on a wrong password. */}
            <Button type="submit" variant="destructive" disabled={deleting}>
              {deleting && <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden />}
              Delete everything
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  );
}
