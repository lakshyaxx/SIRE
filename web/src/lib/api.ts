import type { Workspace, Scope } from '../features/workspace/types';
export type Conversation = { id: string; title: string; created_at: string; updated_at: string };
export type InvestigationJob = {id:string;conversation_id:string;request_id:string;status:'queued'|'running'|'complete'|'partial'|'error'|'cancelled'|'interrupted';events:Record<string,unknown>[];events_total:number;events_trimmed:number;run_id?:string;assistant_message_id?:string;error?:{code:string;message:string}};
export type Evidence = { id: string; modality: string; kind: string; source_id: string; observation: string; locator?: string; reliability: string; limitations: string[] };
export type Tool = { tool: string; status: string; provider?: string; model?: string; elapsed_seconds?: number };
export type Hypothesis = { id: string; mechanism: string; assumptions: string[]; supporting_evidence_ids: string[]; contradicting_evidence_ids: string[]; expected_signs: {predicate: string; expected_value: boolean}[]; missing_tests: string[]; status: string; evidence_support: string; ranking_score: number; falsified_by: string[]; excluded_as_unlinked?: string[] };
export type Investigation = { stop_reason?:string; hypothesis_revisions?: {round:number;candidates:{id:string;status:string;support:string[];conflicts:string[]}[]}[]; id?: string; case: { question: string; evidence: Evidence[] }; hypotheses: Hypothesis[]; rounds: number; unresolved: string[]; limitations: string[] };
export type Meta = {speech_text?:string;claim_verification?:{claim:{category:string;text:string;value?:number;unit?:string;source_ids:string[];observed_at?:string;window_start?:string;window_end?:string};status:string;reason:string;source_value?:number|null}[];narrative_verification?:{status:string;scope:string};generic_report?:{id:string;case_id:string;evidence_ids:string[]}; investigation_id?: string; measurement_profiles?: {groups: {asset_id:string;channel:string;unit:string;count:number;baseline_mean:number;recent_mean:number;delta:number|null;evidence_id:string;series?:{observed_at:string;value:number;source_row:number}[]}[];limitations:string[]}[]; tool_errors?: {code:string;message:string}[]; workspace?: Workspace; context?: Scope; orchestration?: {run_id:string;intent:string}; attachments?: string[]; provider?: string; model?: string; tools?: Tool[]; evidence?: Evidence[]; error?: { code: string; message: string }; investigation?: Investigation; elapsed_seconds?: number };
export type Message = { id: string; role: string; content: string; status: string; metadata: Meta; created_at: string };
export type Attachment = { attachment_id?:string;ingestion_status?:'ready'|'failed';size_bytes?:number;evidence_ids?:string[];evidence_source_ids?:string[];deduplicated?:boolean; id: string; conversation_id: string | null; name: string; kind: string; mime: string; sha256: string; metadata: { transcript?: {text:string;duration_seconds:number;model:string;provider:string}; media_error?: {code:string;message:string}; rows?: number; columns?: string[]; preview?: unknown[]; prediction_eligible?: boolean; declared_dataset?: string; warnings?: string[] } };
export type Detail = Conversation & { messages: Message[]; attachments: Attachment[] };
export type ProviderState = { provider: string; models: { name: string; size: number; digest: string; capabilities?: string[]; details?: { parameter_size?: string } }[]; health: {ollama_ready: boolean; text_ready: boolean; vision_ready: boolean}; configured_text: string; configured_vision: string; retrieval: string };
export type Asset = { asset_id: string; display_name: string; last_cycle: number; rows: number; dataset: string };
export type Model = { model_id: string; family: string; route: string; seed: number; dataset: string; purpose: string; task: string; variant: string; default: boolean; status: string; verification: {error?: string}; artifact_dir: string; feature_schema: string[]; window_length: number | null; historical_metrics: Record<string, unknown> };
export type Prediction = { id: string; dataset: string; model_id: string; purpose: string; asset_id: string | null; attachment_id: string | null; rul_cycles: number | null; interval: number[] | null; interval_method: string | null; last_cycle: number; anomaly: Record<string, unknown> | null; warnings: string[]; target_policy: string; provenance: {version: string; seed: number; runtime: string; artifact_dir: string}; limitations: string[] };
export async function api<T>(path: string, body?: unknown, method?: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { signal, method: method ?? (body === undefined ? 'GET' : 'POST'), ...(body instanceof FormData ? { body } : body !== undefined ? { headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) } : {}) });
  const raw = await response.text();
  let data; try {data = raw ? JSON.parse(raw) : {};} catch {throw new Error(`Server returned an unreadable response (${response.status}). Check that SIRE is running at the correct address.`);}
  if (!response.ok) throw new Error(`${data.error?.message ?? 'Request failed'} (${data.error?.code ?? response.status})`);
  return data as T;
}
export async function streamMessage(body: unknown, signal: AbortSignal, event: (data: Record<string, unknown>) => void) {
  const response = await fetch('/api/v1/chat/message', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body), signal});
  if(response.status===202){event(await response.json());return;}
  if (!response.ok) {const data = await response.json(); throw new Error(data.error?.message ?? 'Chat failed');}
  if (!response.body) throw new Error('Streaming response body unavailable.');
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
  while (true) {const {done, value} = await reader.read(); buffer += decoder.decode(value, {stream: !done}); let index;
    while ((index = buffer.indexOf('\n\n')) >= 0) {const frame = buffer.slice(0,index); buffer = buffer.slice(index+2); for (const line of frame.split('\n')) if (line.startsWith('data: ')) event(JSON.parse(line.slice(6)));}
    if (done) break;
  }
}
