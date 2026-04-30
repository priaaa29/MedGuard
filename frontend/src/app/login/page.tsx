import type { Metadata } from "next";
import { AuthPage } from "@/components/auth-page";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return <AuthPage mode="login" title="Welcome back" intro="Log in to see your medicine routines." />;
}
