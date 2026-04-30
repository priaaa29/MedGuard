import type { Metadata } from "next";
import { AuthPage } from "@/components/auth-page";

export const metadata: Metadata = { title: "Create account" };

export default function SignupPage() {
  return (
    <AuthPage
      mode="signup"
      title="Create your account"
      intro="Your routines are saved to your account so you can come back to them."
    />
  );
}
