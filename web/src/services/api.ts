/** Presentation adapter over SIRE's actual, same-origin API. No synthetic responses. */
import {
  api as request,
  type Investigation,
  type InvestigationJob,
  type Attachment,
} from "../lib/api";
import type {
  Capabilities,
  EvidenceItem,
  InvestigationDetail,
  InvestigationSummary,
  Paged,
  SourceLink,
  StatusResponse,
} from "../types/api";

export const apiBaseUrl =
  typeof location === "undefined" ? "local backend" : location.origin;
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Saved = {
  id: string;
  kind: "case" | "job";
  conversation_id: string;
  created_at: string;
  updated_at: string;
  status: InvestigationSummary["status"];
  question: string;
  evidence_count: number;
  partial_evidence?: Investigation["case"]["evidence"];
  requested_asset_id?: string;
  asset_identity_source?: string;
  attachments?: Array<{
    id: string;
    name: string;
    kind: string;
    missing?: boolean;
  }>;
  failure?: { code: string; message: string; stage?: string };
  report?: Investigation & { id?: string };
  job?: InvestigationJob & { created_at: string; updated_at: string };
};
type Page<T> = { items: T[]; page: number; page_size: number; total: number };
type Health = {
  ml_ready: boolean;
  application_version: string;
  text_ready: boolean;
  vision_ready: boolean;
  ollama_ready: boolean;
};
type Voice = {
  asr_ready: boolean;
  tts_ready: boolean;
  vad_ready?: boolean;
  reason?: string;
};
type Config = {
  checked_at: string;
  max_upload_bytes: number;
  upload_extensions: string[];
};

/** The canonical attachment locator belongs to the evidence record, not Source metadata. */
export function referenceAttachmentId(
  value: Record<string, unknown>,
): string | undefined {
  const evidence = value.evidence as
    | { pointer?: { attachment_id?: unknown } }
    | undefined;
  return typeof evidence?.pointer?.attachment_id === "string"
    ? evidence.pointer.attachment_id
    : undefined;
}

/** Human-readable, source-derived display; the exact full record remains inspectable. */
export function observationText(text: string, kind?: string): string {
  if (kind !== "measurement") return text;
  try {
    const value = JSON.parse(text);
    if (
      value &&
      typeof value === "object" &&
      typeof value.channel === "string" &&
      typeof value.baseline_mean === "number" &&
      typeof value.recent_mean === "number"
    ) {
      const display = (number: number) =>
        Number(number.toPrecision(6)).toString();
      return `${value.asset_id ?? "Asset not supplied"} · ${value.channel.replaceAll("_", " ")}: baseline ${display(value.baseline_mean)} ${value.unit ?? ""}; recent ${display(value.recent_mean)} ${value.unit ?? ""}${typeof value.delta === "number" ? `; change ${display(value.delta)} ${value.unit ?? ""}` : ""}. ${value.count ?? "Unspecified"} source readings. Display rounded to six significant digits; exact windows and values are in the source record.`;
    }
    if (value && typeof value.rows === "number" && Array.isArray(value.columns))
      return `Parsed ${value.rows} source rows and ${value.columns.length} columns. Inspect the source preview for exact cells.${value.prediction_eligible === false ? " This file is not eligible for NASA model inference." : ""}`;
  } catch {
    /* Non-JSON source prose is displayed verbatim. */
  }
  return text;
}

export function presentAttachment(
  item: Attachment & { created_at: string },
): EvidenceItem {
  return {
    id: item.id,
    name: item.name,
    kind: item.kind as EvidenceItem["kind"],
    conversationId: item.conversation_id ?? undefined,
    sizeBytes:
      item.size_bytes ??
      (Number((item.metadata as Record<string, unknown>).size_bytes) ||
        undefined),
    createdAt: item.created_at,
    linkedInvestigationIds: [],
    metadata: {
      sha256: item.sha256,
      mime: item.mime,
      source: "Local upload; authenticity unverified",
    },
    quality: {
      status: item.metadata.media_error
        ? "Extraction failed"
        : "Stored source; observations unverified",
      notes: [
        ...(item.metadata.warnings ?? []),
        ...(item.metadata.media_error
          ? [item.metadata.media_error.message]
          : []),
      ],
    },
    preview: {
      imageUrl:
        item.kind === "image"
          ? `/api/v1/attachments/${item.id}/content`
          : undefined,
      columns: item.metadata.columns,
      rows: item.metadata.preview
        ?.slice(0, 30)
        .map((row) =>
          Array.isArray(row)
            ? row
            : (item.metadata.columns ?? []).map(
                (column) =>
                  (row as Record<string, string | number | null>)[column],
              ),
        ),
    },
    rawMetadata: item.metadata,
  };
}

export function summary(row: Saved): InvestigationSummary {
  return {
    id: row.id,
    title:
      (row.question.length > 96
        ? row.question.slice(0, 93) + "…"
        : row.question) || "Saved investigation",
    question: row.question,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    evidenceCount: row.evidence_count,
    conversationId: row.conversation_id,
  };
}

/** Preserve exact evidence identity and original hypothesis ordering/status. */
export function presentInvestigation(row: Saved): InvestigationDetail {
  const report = row.report;
  const evidence = report?.case.evidence ?? row.partial_evidence ?? [];
  const source = (id: string): SourceLink => ({
    evidenceId: id,
    label: evidence.find((e) => e.id === id)?.locator || "Inspect source",
    locator: evidence.find((e) => e.id === id)?.locator,
  });
  const hypotheses = report?.hypotheses ?? [];
  const events = row.job?.events ?? [];
  const latest = events.filter((e) => e.type === "tool").at(-1);
  const claims = report?.limitations ?? [];
  return {
    ...summary(row),
    caseId: report?.id,
    conversationId: row.conversation_id,
    runId: row.job?.run_id,
    jobId: row.kind === "job" ? row.id : undefined,
    assetId:
      (report?.case as { asset_id?: string } | undefined)?.asset_id ??
      row.requested_asset_id,
    assetIdentitySource:
      row.asset_identity_source ??
      (report?.case as { asset_identity_source?: string } | undefined)
        ?.asset_identity_source,
    attachments: row.attachments,
    error: row.failure,
    stage:
      ["queued", "running"].includes(row.status) && latest
        ? `${String(latest.tool)} · ${String(latest.status)}`
        : row.failure?.stage
          ? `${row.status} · ${row.failure.stage}`
          : row.status,
    summary: report
      ? `${hypotheses.length} proposed mechanisms returned. ${report.stop_reason?.replaceAll("_", " ") ?? ""}.`
      : undefined,
    observations: evidence.map((e) => ({
      id: e.id,
      text: observationText(e.observation, e.kind),
      sources: [source(e.id)],
    })),
    hypotheses: hypotheses.map((h, index) => ({
      id: h.id,
      title: `Proposed mechanism ${index + 1}`,
      classification:
        h.quality_status === "incomplete_text"
          ? "incomplete"
          : h.status === "rejected"
            ? "unsupported"
            : "tentative",
      mechanism: h.mechanism,
      supportingEvidence: h.supporting_evidence_ids.map(source),
      contradictoryEvidence: h.contradicting_evidence_ids.map(source),
      missingInformation: h.assumptions,
      recommendedChecks: h.missing_tests,
      rankingRationale: `${h.evidence_support} evidence support; ${h.status}. Heuristic ordering, not a probability.`,
    })),
    possibleCauses: hypotheses.map((h) => ({
      id: h.id,
      text: h.mechanism,
      confidence: `${h.evidence_support} support · ${h.status}`,
      sources: h.supporting_evidence_ids.map(source),
    })),
    recommendations: hypotheses.flatMap((h) =>
      h.missing_tests.map((text, index) => ({
        id: `${h.id}-check-${index}`,
        text,
        sources: [],
      })),
    ),
    uncertainty: claims.join("\n"),
    followUps: report?.unresolved ?? [],
    activity: events
      .filter((e) =>
        ["started", "plan", "tool", "error", "done", "report"].includes(
          String(e.type),
        ),
      )
      .map((e, index) => ({
        id: String(index),
        at:
          typeof e.timestamp === "string"
            ? e.timestamp
            : typeof e.ended_at === "string"
              ? e.ended_at
              : undefined,
        message:
          e.type === "tool"
            ? `${String(e.tool)}: ${String(e.status)}`
            : e.type === "error"
              ? String(e.message)
              : String(e.type),
      })),
    rawReport: report,
  };
}

async function getSaved(id: string, signal?: AbortSignal): Promise<Saved> {
  return request(
    `/frontend/investigations/${encodeURIComponent(id)}`,
    undefined,
    undefined,
    signal,
  );
}

export const api = {
  capabilities: async (signal?: AbortSignal): Promise<Capabilities> => {
    const [health, voice, config] = await Promise.all([
      request<Health>("/health", undefined, undefined, signal),
      request<Voice>("/voice/capabilities", undefined, undefined, signal),
      request<Config>("/frontend/config", undefined, undefined, signal),
    ]);
    const available = { state: "available" as const };
    return {
      apiVersion: health.application_version,
      checkedAt: config.checked_at,
      investigations: available,
      persistence: available,
      uploads: {
        ...available,
        acceptedTypes: config.upload_extensions,
        maxBytes: config.max_upload_bytes,
      },
      qwen: {
        state: health.text_ready ? "available" : "unavailable",
        reason: health.text_ready
          ? "Configured local text model installed"
          : "Local text provider unavailable",
      },
      kokoro: {
        state: voice.tts_ready ? "available" : "unavailable",
        reason:
          "Local installed-weight readiness; device playback requires browser permission",
      },
      voiceInput: {
        state: voice.asr_ready ? "available" : "unavailable",
        reason:
          "Final local utterance transcription; review automatic recognition",
      },
      cmapss: {
        state: health.ml_ready ? "available" : "unavailable",
        reason: "Preserved native startup inference readiness",
      },
      authorization: {
        canDeleteInvestigations: false,
        canExportInvestigations: true,
      },
    };
  },
  status: async (signal?: AbortSignal): Promise<StatusResponse> => {
    const [health, voice, config] = await Promise.all([
      request<Health>("/health", undefined, undefined, signal),
      request<Voice>("/voice/capabilities", undefined, undefined, signal),
      request<Config>("/frontend/config", undefined, undefined, signal),
    ]);
    return {
      checkedAt: config.checked_at,
      services: [
        {
          name: "SIRE backend",
          state: "operational",
          version: health.application_version,
        },
        {
          name: "Local Qwen text",
          state: health.text_ready ? "operational" : "offline",
          message:
            "Installed configured provider; inference outcomes appear in actual traces",
        },
        {
          name: "Local Qwen vision",
          state: health.vision_ready ? "operational" : "offline",
        },
        {
          name: "Whisper ASR",
          state: voice.asr_ready ? "operational" : "offline",
        },
        {
          name: "Kokoro speech",
          state: voice.tts_ready ? "operational" : "offline",
        },
      ],
    };
  },
  investigations: async (
    params: URLSearchParams,
    signal?: AbortSignal,
  ): Promise<Paged<InvestigationSummary>> => {
    const query = new URLSearchParams({
      page: params.get("page") || "1",
      page_size: params.get("pageSize") || "20",
      query: params.get("query") || "",
      status: params.get("status") || "",
    });
    const data = await request<Page<Saved>>(
      `/frontend/investigations?${query}`,
      undefined,
      undefined,
      signal,
    );
    return {
      items: data.items.map(summary),
      page: data.page,
      pageSize: data.page_size,
      total: data.total,
    };
  },
  investigation: async (id: string, signal?: AbortSignal) =>
    presentInvestigation(await getSaved(id, signal)),
  createInvestigation: async (
    form: FormData,
    signal?: AbortSignal,
  ): Promise<InvestigationSummary> => {
    const question = String(form.get("question") ?? "").trim();
    if (!question) throw new ApiError("Enter an investigation question.");
    const conversation = await request<{ id: string }>(
      "/conversations",
      { title: question.slice(0, 100) },
      undefined,
      signal,
    );
    window.dispatchEvent(new Event("sire:conversations-changed"));
    const ids: string[] = [];
    for (const file of form.getAll("evidence")) {
      if (!(file instanceof File)) continue;
      const upload = new FormData();
      upload.set("conversation_id", conversation.id);
      upload.set("file", file, file.name);
      const receipt = await request<Attachment>(
        "/attachments",
        upload,
        undefined,
        signal,
      );
      if (receipt.ingestion_status === "failed" || receipt.metadata.media_error)
        throw new ApiError(
          receipt.metadata.media_error?.message ||
            "File extraction failed. The saved conversation retains the original upload.",
        );
      ids.push(receipt.id);
    }
    const context = String(form.get("context") ?? "").trim();
    const job = await request<
      InvestigationJob & { created_at: string; updated_at: string }
    >(
      "/investigation-jobs",
      {
        conversation_id: conversation.id,
        request_id: crypto.randomUUID(),
        content: context
          ? `${question}\n\nUser-supplied context: ${context}`
          : question,
        attachment_ids: ids,
        mode: "investigate",
      },
      undefined,
      signal,
    );
    window.dispatchEvent(new Event("sire:conversations-changed"));
    return {
      id: job.id,
      title: question.slice(0, 96),
      question,
      status: job.status,
      createdAt: job.created_at,
      updatedAt: job.updated_at,
      evidenceCount: ids.length,
      conversationId: conversation.id,
    };
  },
  cancelInvestigation: async (id: string) => {
    const row = await getSaved(id);
    if (row.kind !== "job")
      throw new ApiError("This saved case has no active job.");
    return request(
      `/investigation-jobs/${encodeURIComponent(id)}/cancel?conversation_id=${encodeURIComponent(row.conversation_id)}`,
      {},
    );
  },
  exportInvestigation: async (id: string, signal?: AbortSignal) => {
    const row = await getSaved(id, signal);
    const caseId = row.report?.id;
    if (!caseId)
      throw new ApiError(
        "A completed saved case is required before exporting.",
      );
    const report = await request<{ id: string }>(
      `/evidence-investigations/${encodeURIComponent(caseId)}/report`,
      {},
      undefined,
      signal,
    );
    const response = await fetch(
      `/api/v1/reports/${encodeURIComponent(report.id)}/download?format=pdf`,
      { signal },
    );
    if (!response.ok)
      throw new ApiError("Report download failed.", response.status);
    return response.blob();
  },
  evidence: async (
    signal?: AbortSignal,
    page = 1,
    query = "",
    kind = "",
  ): Promise<Paged<EvidenceItem>> => {
    const data = await request<Page<Attachment & { created_at: string }>>(
      `/frontend/attachments?${new URLSearchParams({ page: String(page), page_size: "30", query, kind })}`,
      undefined,
      undefined,
      signal,
    );
    return {
      items: data.items.map(presentAttachment),
      page: data.page,
      pageSize: data.page_size,
      total: data.total,
    };
  },
  attachment: async (id: string, signal?: AbortSignal) =>
    presentAttachment(
      await request<Attachment & { created_at: string }>(
        `/frontend/attachments/${encodeURIComponent(id)}`,
        undefined,
        undefined,
        signal,
      ),
    ),
  resolveEvidence: (id: string, signal?: AbortSignal) =>
    request<Record<string, unknown>>(
      `/evidence/${encodeURIComponent(id)}`,
      undefined,
      undefined,
      signal,
    ),
  attachmentSections: (conversationId: string, signal?: AbortSignal) =>
    request<{
      chunks: { attachment_id: string; locator: string; text: string }[];
    }>(
      `/knowledge/sources?conversation_id=${encodeURIComponent(conversationId)}`,
      undefined,
      undefined,
      signal,
    ),
};
