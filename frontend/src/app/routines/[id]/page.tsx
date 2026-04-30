import type { Metadata } from "next";
import { Suspense } from "react";
import { RoutineDetail } from "@/components/routines/routine-detail";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Routine" };

export default function RoutinePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 md:px-6">
      {/* RoutineDetail reads the [id] param with useParams, which needs a boundary under Cache Components. */}
      <Suspense fallback={<Skeleton className="h-96 w-full rounded-xl" />}>
        <RoutineDetail />
      </Suspense>
    </div>
  );
}
