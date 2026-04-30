import { Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { RoutineList } from "@/components/routines/routine-list";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "My routines" };

export default function RoutinesPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 md:px-6">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">My routines</h1>
          <p className="mt-1 text-muted-foreground">Saved timetables for your medicines.</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/routines/new">
            <Plus data-icon="inline-start" aria-hidden />
            New routine
          </Link>
        </Button>
      </div>
      <RoutineList />
    </div>
  );
}
