import type { Metadata } from "next";
import { NewRoutineWizard } from "@/components/routines/new-routine-wizard";

export const metadata: Metadata = { title: "New routine" };

export default function NewRoutinePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 md:px-6">
      <NewRoutineWizard />
    </div>
  );
}
