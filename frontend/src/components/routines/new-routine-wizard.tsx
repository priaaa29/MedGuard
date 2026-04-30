"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { DEFAULT_SCHEDULE, emptyDraft, fromExtracted, toMedication } from "@/components/routines/draft";
import type { DraftMedication } from "@/components/routines/draft";
import { GeneratingStep } from "@/components/routines/generating-step";
import { PrescriptionStep } from "@/components/routines/prescription-step";
import { ReviewStep } from "@/components/routines/review-step";
import { ScheduleStep } from "@/components/routines/schedule-step";
import { Stepper } from "@/components/routines/stepper";
import { api, ApiError } from "@/lib/api";
import type { DailySchedule, PrescriptionExtraction } from "@/lib/types";

type Step = "prescription" | "review" | "schedule" | "generating";
const STEP_INDEX: Record<Step, number> = { prescription: 0, review: 1, schedule: 2, generating: 3 };

export function NewRoutineWizard() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("prescription");
  const [drafts, setDrafts] = useState<DraftMedication[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [schedule, setSchedule] = useState<DailySchedule>(DEFAULT_SCHEDULE);
  const [title, setTitle] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // Move focus to the page heading on each step change so screen readers and
  // keyboard users start at the top of the new step.
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
    window.scrollTo({ top: 0 });
  }, [step]);

  const toLogin = () => router.replace("/login?next=/routines/new");

  function onExtracted(result: PrescriptionExtraction) {
    setDrafts(result.medications.map(fromExtracted));
    setWarnings(result.warnings);
    setStep("review");
  }

  function onManual() {
    setDrafts(drafts.length ? drafts : [emptyDraft()]);
    setWarnings([]);
    setStep("review");
  }

  async function build() {
    setSubmitError(null);
    setStep("generating");
    try {
      const routine = await api.createRoutine(drafts.map(toMedication), schedule, title.trim());
      router.push(`/routines/${routine.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return toLogin();
      setSubmitError(error instanceof ApiError ? error.message : "Something went wrong.");
      setStep("schedule");
    }
  }

  return (
    <div className="space-y-8">
      <div className="space-y-4">
        <h1 ref={headingRef} tabIndex={-1} className="text-3xl font-semibold tracking-tight focus:outline-none">
          New routine
        </h1>
        <Stepper current={Math.min(STEP_INDEX[step], 2)} />
      </div>

      {step === "prescription" && (
        <PrescriptionStep onExtracted={onExtracted} onManual={onManual} onUnauthorized={toLogin} />
      )}
      {step === "review" && (
        <ReviewStep
          drafts={drafts}
          warnings={warnings}
          onChange={setDrafts}
          onBack={() => setStep("prescription")}
          onContinue={() => setStep("schedule")}
        />
      )}
      {step === "schedule" && (
        <ScheduleStep
          schedule={schedule}
          title={title}
          submitError={submitError}
          onChange={setSchedule}
          onTitleChange={setTitle}
          onBack={() => setStep("review")}
          onSubmit={build}
        />
      )}
      {step === "generating" && <GeneratingStep />}
    </div>
  );
}
