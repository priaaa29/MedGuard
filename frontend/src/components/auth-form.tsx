"use client";

import { Eye, EyeOff, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";

const PASSWORD_MIN = 10;

type Mode = "login" | "signup";
type Errors = { email?: string; password?: string; form?: string };

/** Only follow same-site paths, so ?next= can't be used as an open redirect. */
function safeNext(value: string | null) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/routines";
}

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [submitting, setSubmitting] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const isSignup = mode === "signup";
  const next = safeNext(searchParams.get("next"));

  function validate(): Errors {
    const found: Errors = {};
    if (!email.includes("@")) found.email = "Enter an email address like name@example.com.";
    if (!password) found.password = "Enter your password.";
    else if (isSignup && password.length < PASSWORD_MIN)
      found.password = `Use at least ${PASSWORD_MIN} characters.`;
    return found;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (found.email) return emailRef.current?.focus();
    if (found.password) return passwordRef.current?.focus();

    setSubmitting(true);
    try {
      const user = isSignup ? await api.register(email, password) : await api.login(email, password);
      setUser(user);
      router.replace(isSignup ? "/routines/new" : next);
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError(0, "Something went wrong.");
      const fieldErrors: Errors = {
        email: apiError.fieldErrors.email,
        password: apiError.fieldErrors.password,
      };
      if (apiError.status === 409) fieldErrors.email = apiError.message;
      if (!fieldErrors.email && !fieldErrors.password) fieldErrors.form = apiError.message;
      setErrors(fieldErrors);
      if (fieldErrors.email) emailRef.current?.focus();
      else if (fieldErrors.password) passwordRef.current?.focus();
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate aria-busy={submitting}>
      <FieldGroup>
        {errors.form && (
          <Alert variant="destructive" role="alert">
            <AlertDescription>{errors.form}</AlertDescription>
          </Alert>
        )}

        <Field data-invalid={errors.email ? true : undefined}>
          <FieldLabel htmlFor="email">Email</FieldLabel>
          <Input
            ref={emailRef}
            id="email"
            type="email"
            autoComplete="email"
            spellCheck={false}
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={errors.email ? "email-error" : undefined}
            autoFocus
          />
          {errors.email && <FieldError id="email-error">{errors.email}</FieldError>}
        </Field>

        <Field data-invalid={errors.password ? true : undefined}>
          <div className="flex items-center justify-between">
            <FieldLabel htmlFor="password">Password</FieldLabel>
          </div>
          <div className="relative">
            <Input
              ref={passwordRef}
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete={isSignup ? "new-password" : "current-password"}
              spellCheck={false}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="pr-12"
              aria-invalid={errors.password ? true : undefined}
              aria-describedby={
                [isSignup ? "password-hint" : null, errors.password ? "password-error" : null]
                  .filter(Boolean)
                  .join(" ") || undefined
              }
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute top-0 right-0 text-muted-foreground"
              onClick={() => setShowPassword((value) => !value)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              aria-pressed={showPassword}
            >
              {showPassword ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
            </Button>
          </div>
          {isSignup && (
            <FieldDescription id="password-hint">
              At least {PASSWORD_MIN} characters.{" "}
              <span className="font-mono tabular-nums">
                {password.length}/{PASSWORD_MIN}
              </span>
            </FieldDescription>
          )}
          {errors.password && <FieldError id="password-error">{errors.password}</FieldError>}
        </Field>

        <Button type="submit" size="lg" disabled={submitting} className="w-full">
          {submitting && <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden />}
          {isSignup ? "Create account" : "Log in"}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          {isSignup ? "Already have an account? " : "New to MedGuard? "}
          <Link
            href={isSignup ? "/login" : `/signup${next !== "/routines" ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="font-medium text-primary underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {isSignup ? "Log in" : "Create an account"}
          </Link>
        </p>
      </FieldGroup>
    </form>
  );
}
