import { CalendarClock, FileText, ShieldCheck, Utensils } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const STEPS = [
  {
    icon: FileText,
    title: "Add your prescription",
    body: "Upload a photo or PDF, or type it in. You check every medicine before anything else happens.",
  },
  {
    icon: Utensils,
    title: "See what to avoid",
    body: "Food, drink and medicine combinations that can weaken a medicine or cause side effects.",
  },
  {
    icon: CalendarClock,
    title: "Get a daily routine",
    body: "Times that fit your day, with safe gaps between medicines that shouldn't be taken together.",
  },
];

const PROMISES = [
  "Doses and amounts always come from your prescription. MedGuard only suggests times.",
  "Every timetable is checked against timing rules before you see it.",
  "Anything flagged by AI is labelled, so you know where it came from.",
];

const SAMPLE = [
  { time: "07:15", name: "Levothyroxine", note: "45 min before breakfast" },
  { time: "08:00", name: "Metformin", note: "With breakfast" },
  { time: "14:00", name: "Calcium", note: "4 h after levothyroxine" },
  { time: "20:00", name: "Metformin", note: "With dinner" },
];

export default function Home() {
  return (
    <>
      <section className="mx-auto grid max-w-5xl items-center gap-12 px-4 py-16 md:grid-cols-[1.1fr_1fr] md:px-6 md:py-24">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight text-balance md:text-5xl">
            Your medicines, safely timed.
          </h1>
          <p className="mt-5 max-w-prose text-lg leading-8 text-muted-foreground">
            MedGuard reads your prescription, checks for food and drug interactions, and builds a daily routine with
            the right gaps between doses, ready to review with your pharmacist.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/signup">Get started</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/login">Log in</Link>
            </Button>
          </div>
        </div>

        <figure className="rounded-xl border border-border bg-card p-5 shadow-sm" aria-label="Example daily routine">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium">Today&apos;s routine</p>
            <Badge variant="success">Checked</Badge>
          </div>
          <ol className="mt-4 divide-y divide-border">
            {SAMPLE.map((dose) => (
              <li key={`${dose.time}-${dose.name}`} className="flex items-baseline gap-4 py-3">
                <span className="w-14 shrink-0 font-mono text-sm font-semibold tabular-nums">{dose.time}</span>
                <span className="min-w-0">
                  <span className="block font-medium">{dose.name}</span>
                  <span className="block text-sm text-muted-foreground">{dose.note}</span>
                </span>
              </li>
            ))}
          </ol>
          <figcaption className="mt-3 text-sm text-muted-foreground">Example only.</figcaption>
        </figure>
      </section>

      <section className="border-t border-border bg-card" aria-labelledby="how-heading">
        <div className="mx-auto max-w-5xl px-4 py-16 md:px-6">
          <h2 id="how-heading" className="text-xl font-semibold">
            How it works
          </h2>
          <ol className="mt-8 grid gap-8 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <div className="flex items-center gap-3">
                  <span className="flex size-10 items-center justify-center rounded-lg bg-secondary text-primary">
                    <step.icon className="size-5" aria-hidden />
                  </span>
                  <span className="font-mono text-sm text-muted-foreground">0{index + 1}</span>
                </div>
                <h3 className="mt-4 font-medium">{step.title}</h3>
                <p className="mt-2 text-muted-foreground">{step.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-16 md:px-6" aria-labelledby="safety-heading">
        <div className="flex items-start gap-4">
          <ShieldCheck className="mt-1 size-6 shrink-0 text-primary" aria-hidden />
          <div>
            <h2 id="safety-heading" className="text-xl font-semibold">
              Built to be careful
            </h2>
            <ul className="mt-4 space-y-3 text-muted-foreground">
              {PROMISES.map((promise) => (
                <li key={promise} className="max-w-prose">
                  {promise}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </>
  );
}
