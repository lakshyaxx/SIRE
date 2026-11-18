export type CapabilityState = "available" | "unavailable" | "unverified";

export interface Capability {
  state: CapabilityState;
  reason?: string;
  model?: string;
  version?: string;
}

export interface Attachment {
  id: string;
  name: string;
  type: string;
  sizeBytes: number;
  status: "ready" | "uploading" | "complete" | "error";
  progress?: number;
  error?: string;
}

export interface Case {
  id: string;
  title: string;
  assetId?: string;
  incidentAt?: string;
  status: InvestigationSummary["status"];
  updatedAt: string;
  evidenceCount: number;
}

export interface Evidence {
  id: string;
  name: string;
  modality: "image" | "pdf" | "csv" | "xlsx" | "audio" | "video" | "unknown";
  assetId?: string;
  recordedAt?: string;
  originGroup?: string;
  relation?: "supporting" | "contradictory" | "context";
}

export interface Hypothesis {
  id: string;
  title: string;
  classification:
    | "observed"
    | "model-inferred"
    | "tentative"
    | "simulated"
    | "unsupported"
    | "incomplete";
  mechanism?: string;
  supportingEvidence: SourceLink[];
  contradictoryEvidence: SourceLink[];
  missingInformation: string[];
  recommendedChecks: string[];
  rankingRationale?: string;
}

export interface InvestigationJob {
  id: string;
  status: InvestigationSummary["status"];
  stage?: string;
  startedAt?: string;
  updatedAt: string;
  elapsedMs?: number;
}

export interface PredictionInput {
  dataset?: "FD001" | "FD002" | "FD003" | "FD004";
  model?: string;
  unitId?: string;
  sequenceWindow?: number;
  values: Record<string, number>;
}

export type PredictionResult = CmapssPrediction;

export interface VoiceSession {
  id: string;
  state:
    | "ready"
    | "requesting-permission"
    | "connecting"
    | "listening"
    | "processing"
    | "speaking"
    | "muted"
    | "interrupted"
    | "reconnecting"
    | "ended"
    | "permission-denied"
    | "unavailable";
  turnId?: string;
}

export interface VoiceEvent {
  sessionId: string;
  turnId: string;
  sequence: number;
  type: string;
  timestamp: string;
  payload: unknown;
}

export type ProviderStatus = ServiceStatus;

export interface Capabilities {
  apiVersion: string;
  checkedAt: string;
  investigations: Capability;
  persistence: Capability;
  uploads: Capability & { acceptedTypes?: string[]; maxBytes?: number };
  qwen: Capability;
  kokoro: Capability;
  voiceInput: Capability;
  cmapss: Capability;
  authorization: {
    canDeleteInvestigations: boolean;
    canExportInvestigations: boolean;
  };
}

export interface InvestigationSummary {
  id: string;
  title: string;
  question: string;
  status:
    | "queued"
    | "running"
    | "complete"
    | "failed"
    | "cancelled"
    | "partial"
    | "error"
    | "interrupted";
  conversationId?: string;
  createdAt: string;
  updatedAt: string;
  evidenceCount: number;
}

export interface SourceLink {
  evidenceId: string;
  label: string;
  locator?: string;
}

export interface InvestigationDetail extends InvestigationSummary {
  error?: { code: string; message: string; stage?: string };
  assetIdentitySource?: string;
  attachments?: Array<{
    id: string;
    name: string;
    kind: string;
    missing?: boolean;
  }>;
  runId?: string;
  jobId?: string;
  rawReport?: unknown;
  caseId?: string;
  assetId?: string;
  incidentAt?: string;
  stage?: string;
  elapsedMs?: number;
  hypotheses?: Hypothesis[];
  summary?: string;
  observations: Array<{ id: string; text: string; sources: SourceLink[] }>;
  interpretation?: string;
  possibleCauses: Array<{
    id: string;
    text: string;
    confidence?: string;
    sources: SourceLink[];
  }>;
  recommendations: Array<{
    id: string;
    text: string;
    priority?: string;
    sources: SourceLink[];
  }>;
  uncertainty?: string;
  explanations?: { plain?: string; technical?: string };
  followUps: string[];
  activity: Array<{ id: string; at?: string; message: string }>;
}

export interface EvidenceItem {
  id: string;
  name: string;
  kind: "csv" | "image" | "document" | "audio" | "video";
  conversationId?: string;
  rawMetadata?: unknown;
  sizeBytes?: number;
  createdAt: string;
  linkedInvestigationIds: string[];
  metadata: Record<string, string | number | boolean | null>;
  quality?: { status: string; notes: string[] };
  preview?: {
    columns?: string[];
    rows?: Array<Array<string | number | boolean | null>>;
    imageUrl?: string;
  };
}

export interface Paged<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface ServiceStatus {
  name: string;
  state: "operational" | "degraded" | "offline" | "unverified";
  model?: string;
  version?: string;
  latencyMs?: number;
  message?: string;
}

export interface StatusResponse {
  checkedAt: string;
  services: ServiceStatus[];
}

export interface CmapssSchema {
  fields: Array<{
    name: string;
    label: string;
    type: "number" | "integer";
    required: boolean;
    unit?: string;
    min?: number;
    max?: number;
  }>;
  model: {
    name: string;
    version?: string;
    description?: string;
    limitations: string[];
  };
}

export interface CmapssPrediction {
  remainingUsefulLife: number;
  unit: string;
  interval?: { lower: number; upper: number; level: string };
  actualRul?: number;
  trend?: Array<{ cycle: number; predictedRul: number; actualRul?: number }>;
  comparisons?: Array<{ label: string; value: number; unit: string }>;
  metrics?: Array<{
    name: string;
    value: number;
    unit?: string;
    scope: string;
  }>;
  limitations: string[];
}
