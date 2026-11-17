export type Scope = { scenario_id: string; asset_id: string; as_of?: string; case_id?: string | null };
export type Scenario = { id: string; name: string; asset_id: string; starts_at: string; reference_at: string; ends_at: string };
export type FacilityHypothesis = { id: string; mechanism: string; status: string; score: number; support: string[]; contradictions: string[]; missing_measurements: string[]; next_checks: string[] };
export type FacilityCase = { id: string; scenario_id: string; asset_id: string; as_of: string; conclusion: string; hypotheses: FacilityHypothesis[]; evidence_ids: string[]; run_id: string; chronology: { id: string; text: string; observed_at: string; available_at: string; evidence_id: string }[]; stop_reason: string; limitations: string[] };
export type Channel = { unit: string; baseline_mean: number | null; recent_mean: number | null; delta: number | null; missing_count: number; valid_count: number; evidence_id: string; available: boolean };
export type Workspace = { context: Scope; source_type: string; evidence_ids: string[]; errors: {tool: string; code: string; message: string}[]; outputs: {
  'facility.investigate'?: {case: FacilityCase};
  'temporal.summary'?: {channels: Record<string, Channel>};
  'case.report'?: {report: {id: string; sha256: string; created_at: string}};
  'case.similar'?: {cases: SimilarCase[]};
} };
export type SimilarCase = { case_id: string; asset_id: string; overlap_score: number; shared_mechanisms: string[]; different_mechanisms: string[]; caveat: string };
