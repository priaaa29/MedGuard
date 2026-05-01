"use client";

import { AlertCircle, FileUp, Loader2, PencilLine, ShieldAlert } from "lucide-react";
import { useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { PrescriptionExtraction } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_BYTES = 10 * 1024 * 1024;
const MAX_TEXT = 5000;
const ACCEPT = "image/jpeg,image/png,image/webp,image/gif,application/pdf";
const ACCEPTED_TYPES = ACCEPT.split(",");

type Props = {
  onExtracted: (result: PrescriptionExtraction) => void;
  onManual: () => void;
  onUnauthorized: () => void;
};

export function PrescriptionStep({ onExtracted, onManual, onUnauthorized }: Props) {
  const [tab, setTab] = useState<"upload" | "type">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [notPrescription, setNotPrescription] = useState(false);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function pickFile(candidate: File | undefined) {
    setFieldError(null);
    setNotPrescription(false);
    if (!candidate) return;
    if (!ACCEPTED_TYPES.includes(candidate.type)) {
      setFieldError("Choose a JPEG, PNG, WebP or GIF photo, or a PDF.");
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setFieldError("That file is over 10 MB. Try a smaller photo or a screenshot.");
      return;
    }
    setFile(candidate);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    pickFile(event.dataTransfer.files[0]);
  }

  async function read() {
    setRequestError(null);
    setNotPrescription(false);
    if (tab === "upload" && !file) return setFieldError("Choose a photo or PDF of your prescription.");
    if (tab === "type" && !text.trim()) return setFieldError("Type or paste your prescription.");

    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const result =
        tab === "upload" ? await api.extractFromFile(file!, controller.signal) : await api.extractFromText(text, controller.signal);
      if (!result.is_prescription || result.medications.length === 0) {
        setNotPrescription(true);
        return;
      }
      onExtracted(result);
    } catch (error) {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) return onUnauthorized();
      setRequestError(error instanceof ApiError ? error.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-xl border border-border bg-card px-6 py-16 text-center" role="status">
        <Loader2 className="size-8 animate-spin text-primary motion-reduce:animate-none" aria-hidden />
        <div className="space-y-1">
          <p className="font-medium">Reading your prescription…</p>
          <p className="text-sm text-muted-foreground">This usually takes 10 to 30 seconds.</p>
        </div>
        <Button variant="outline" onClick={() => abortRef.current?.abort()}>
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Tabs
        value={tab}
        onValueChange={(value) => {
          setTab(value as "upload" | "type");
          setFieldError(null);
        }}
      >
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="upload" className="flex-1 sm:flex-none">
            <FileUp aria-hidden />
            Upload
          </TabsTrigger>
          <TabsTrigger value="type" className="flex-1 sm:flex-none">
            <PencilLine aria-hidden />
            Type it
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upload" className="mt-4">
          <Field data-invalid={fieldError ? true : undefined}>
            <FieldLabel htmlFor="prescription-file" className="sr-only">
              Prescription photo or PDF
            </FieldLabel>
            <label
              htmlFor="prescription-file"
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                "flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors has-focus-visible:ring-2 has-focus-visible:ring-ring",
                dragging ? "border-primary bg-accent" : "border-border bg-card hover:bg-accent",
              )}
            >
              <FileUp className="size-8 text-primary" aria-hidden />
              {file ? (
                <span>
                  <span className="block font-medium break-all">{file.name}</span>
                  <span className="block text-sm text-muted-foreground">Choose a different file</span>
                </span>
              ) : (
                <span>
                  <span className="block font-medium">Choose a photo or PDF</span>
                  <span className="block text-sm text-muted-foreground">or drag it here · up to 10 MB</span>
                </span>
              )}
              <input
                id="prescription-file"
                type="file"
                accept={ACCEPT}
                className="sr-only"
                onChange={(event: ChangeEvent<HTMLInputElement>) => pickFile(event.target.files?.[0])}
                aria-describedby={fieldError ? "file-error" : "file-hint"}
                aria-invalid={fieldError ? true : undefined}
              />
            </label>
            <FieldDescription id="file-hint">
              A clear, flat photo in good light works best. MedGuard doesn&apos;t store the file.
            </FieldDescription>
            {fieldError && <FieldError id="file-error">{fieldError}</FieldError>}
          </Field>
        </TabsContent>

        <TabsContent value="type" className="mt-4">
          <Field data-invalid={fieldError ? true : undefined}>
            <FieldLabel htmlFor="prescription-text">Prescription</FieldLabel>
            <Textarea
              id="prescription-text"
              rows={8}
              maxLength={MAX_TEXT}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={"Tab Metformin 500 mg  1-0-1  after food\nTab Levothyroxine 50 mcg  1-0-0  empty stomach"}
              className="min-h-40 font-mono text-sm"
              aria-describedby={fieldError ? "text-error" : "text-hint"}
              aria-invalid={fieldError ? true : undefined}
            />
            <FieldDescription id="text-hint">
              Copy it as written, shorthand like BD or 1-0-1 is fine.{" "}
              <span className="font-mono tabular-nums">
                {text.length}/{MAX_TEXT}
              </span>
            </FieldDescription>
            {fieldError && <FieldError id="text-error">{fieldError}</FieldError>}
          </Field>
        </TabsContent>
      </Tabs>

      {/* Google's free Gemini tier may use inputs to improve its products, with human review. */}
      <div className="flex gap-3 rounded-lg border border-border bg-muted px-4 py-3 text-sm">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
        <p>
          <span className="font-medium">Before you upload:</span> MedGuard uses Google&apos;s Gemini AI to read
          prescriptions. On its free service, Google may use what you send to improve its products, and people at
          Google may review it. Cover your name, address and doctor&apos;s details first, or type just the medicine
          lines instead.
        </p>
      </div>

      {notPrescription && (
        <Alert variant="warning" role="alert">
          <AlertCircle aria-hidden />
          <AlertTitle>No medicines found</AlertTitle>
          <AlertDescription>
            This doesn&apos;t look like a prescription or medicine list. Try a clearer photo, type it in, or add your
            medicines by hand.
          </AlertDescription>
        </Alert>
      )}

      {requestError && (
        <Alert variant="destructive" role="alert">
          <AlertCircle aria-hidden />
          <AlertTitle>Couldn&apos;t read the prescription</AlertTitle>
          <AlertDescription>{requestError}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Button variant="ghost" onClick={onManual}>
          Enter medicines by hand instead
        </Button>
        <Button size="lg" onClick={read}>
          Read prescription
        </Button>
      </div>
    </div>
  );
}
