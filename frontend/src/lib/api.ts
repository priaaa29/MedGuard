import type {
  DailySchedule,
  Medication,
  PrescriptionExtraction,
  RoutineDetail,
  RoutineSummary,
  User,
} from "@/lib/types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Per-field messages from FastAPI 422 responses, keyed by the last path segment. */
    public fieldErrors: Record<string, string> = {},
  ) {
    super(message);
  }
}

type FastApiValidationItem = { loc: (string | number)[]; msg: string };

const FALLBACK: Record<number, string> = {
  401: "Please log in to continue.",
  404: "We couldn't find that.",
  413: "That file is too large.",
  429: "Too many requests. Please wait a minute and try again.",
  502: "The AI service had a problem. Please try again.",
};

function cleanPydanticMessage(msg: string) {
  return msg.replace(/^Value error, /, "");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", ...init });
  } catch {
    throw new ApiError(0, "Can't reach MedGuard. Check your connection and try again.");
  }

  if (response.status === 204) return undefined as T;

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON error (e.g. proxy timeout). Fall through to the generic message.
  }

  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (Array.isArray(detail)) {
      const items = detail as FastApiValidationItem[];
      const fieldErrors: Record<string, string> = {};
      for (const item of items) {
        const key = String(item.loc.at(-1) ?? "form");
        fieldErrors[key] ??= cleanPydanticMessage(item.msg);
      }
      throw new ApiError(response.status, cleanPydanticMessage(items[0]?.msg ?? "Please check the form."), fieldErrors);
    }
    const message =
      typeof detail === "string"
        ? detail
        : (FALLBACK[response.status] ??
          (response.status >= 500 ? "Something went wrong on our side. Please try again." : "Request failed."));
    throw new ApiError(response.status, message);
  }

  return body as T;
}

function json(method: string, data: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) };
}

export const api = {
  me: () => request<User>("/api/auth/me"),
  register: (email: string, password: string) => request<User>("/api/auth/register", json("POST", { email, password })),
  login: (email: string, password: string) => request<User>("/api/auth/login", json("POST", { email, password })),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  deleteAccount: (password: string) => request<void>("/api/auth/me", json("DELETE", { password })),

  extractFromFile: (file: File, signal?: AbortSignal) => {
    const form = new FormData();
    form.append("file", file);
    return request<PrescriptionExtraction>("/api/prescriptions/extract", { method: "POST", body: form, signal });
  },
  extractFromText: (text: string, signal?: AbortSignal) => {
    const form = new FormData();
    form.append("text", text);
    return request<PrescriptionExtraction>("/api/prescriptions/extract", { method: "POST", body: form, signal });
  },

  createRoutine: (medications: Medication[], schedule: DailySchedule, title?: string) =>
    request<RoutineDetail>("/api/routines", json("POST", { medications, schedule, title: title || undefined })),
  retryRoutine: (id: string) =>
    request<RoutineDetail>(`/api/routines/${encodeURIComponent(id)}/retry`, { method: "POST" }),
  listRoutines: () => request<RoutineSummary[]>("/api/routines"),
  getRoutine: (id: string) => request<RoutineDetail>(`/api/routines/${encodeURIComponent(id)}`),
  renameRoutine: (id: string, title: string) =>
    request<RoutineSummary>(`/api/routines/${encodeURIComponent(id)}`, json("PATCH", { title })),
  deleteRoutine: (id: string) => request<void>(`/api/routines/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
