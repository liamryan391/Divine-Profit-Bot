export type JsonMap = Record<string, unknown>;

export interface AuthAccount {
  id: number;
  username: string;
  display_name?: string;
  role: string;
  recovery_email?: string;
  created_at?: string;
  last_login_at?: string;
  disabled?: boolean;
}

export interface AuthStatus {
  enabled: boolean;
  setup_required: boolean;
  authenticated: boolean;
  account: AuthAccount | null;
  accounts?: AuthAccount[];
  secret_management?: JsonMap;
}

export interface WorkerStatus {
  worker_name?: string;
  state: string;
  last_seen_at?: string | null;
  age_seconds: number | null;
  detail?: string;
  stale_after_seconds?: number;
}

export interface Temple {
  id: string;
  name: string;
  description?: string;
  template?: string;
  active?: boolean;
}

export interface TempleSummaryRow {
  id: string;
  name: string;
  active: boolean;
  judgement: string;
  top_strategy: string;
  earned: string;
  quota: string;
  progress_pct: number;
  mood: string;
}

export interface TempleSummary {
  temple_count: number;
  overall_progress_pct: number;
  total_earned_minor: number;
  rows: TempleSummaryRow[];
}

export interface StatusReport {
  god_name: string;
  temple?: Temple;
  mood: string;
  period: {
    name: string;
    start: string;
    end: string;
  };
  quota_minor: number;
  earned_minor: number;
  remaining_minor: number;
  quota: string;
  earned: string;
  remaining: string;
  progress: number;
  progress_pct: number;
  days_left: number;
  judgement: string;
  punishment?: string;
  exception?: unknown;
}

export interface StrategyChannel {
  id?: string;
  name: string;
  expected_gbp_minor?: number;
  effort?: string;
  risk?: string;
  next_action?: string;
}

export interface ConfigPayload {
  god_name: string;
  active_mood: string;
  base_currency: string;
  active_temple?: Temple;
  temples: Temple[];
  strategy_templates: JsonMap;
  moods: Record<string, JsonMap>;
  channels: StrategyChannel[];
}

export interface Opportunity {
  id: string;
  rank: number;
  name: string;
  expected: string;
  period_income: string;
  score: number;
  score_label: string;
  fit?: string;
  risk?: string;
  rationale: string;
  next_action: string;
  components: Record<string, number>;
}

export interface StrategyRoiRow {
  id: string;
  name: string;
  roi_rank: number;
  trend: string;
  target_capture_pct: number;
  recommendation: string;
  recommendation_reason: string;
  current_period: string;
  previous_period: string;
  delta: string;
  roi_per_effort: string;
  notes: Array<{ amount: string; note: string }>;
}

export interface StrategyRoi {
  period: {
    start: string;
    end: string;
  };
  rows: StrategyRoiRow[];
  push_recommendations: StrategyRoiRow[];
  pause_recommendations: StrategyRoiRow[];
}

export interface IncomeEntry {
  id: number;
  lead_id?: number | null;
  amount: string;
  counted: string;
  currency: string;
  source: string;
  strategy?: string;
  note?: string;
  occurred_at: string;
}

export interface EventEntry {
  id?: number;
  category: string;
  message: string;
  created_at: string;
}

export interface ReportPayload {
  title: string;
  markdown: string;
  earned: string;
  quota: string;
  period: {
    start: string;
    end: string;
  };
}

export interface ApprovalAction {
  id: number;
  kind: string;
  kind_label: string;
  title: string;
  body: string;
  status: string;
  strategy?: string;
}

export interface ApprovalSummary {
  counts: Record<string, number>;
  recent: ApprovalAction[];
}

export interface LeadStageSummary {
  id: string;
  label: string;
  count: number;
  value: string;
}

export interface LeadEntry {
  id: number;
  title: string;
  contact?: string;
  source?: string;
  offer: string;
  estimated_value: string;
  estimated_value_minor: number;
  weighted_value: string;
  weighted_value_minor: number;
  probability: number;
  probability_pct: number;
  stage: string;
  stage_label: string;
  converted_income_id?: number | null;
  converted_gbp_minor?: number | null;
  converted_at?: string | null;
  converted_source?: string | null;
  strategy?: string;
  next_action?: string;
  follow_up_on?: string;
  follow_up_state: string;
  days_until_follow_up: number | null;
  notes?: string;
  created_at?: string;
  updated_at?: string;
  closed_at?: string;
  priority_score: number;
  priority_label: string;
  priority_components: Record<string, number>;
}

export interface LeadPipelineSummary {
  stages: LeadStageSummary[];
  counts: Record<string, number>;
  open_count: number;
  total_count: number;
  due_count: number;
  total_estimated_value: string;
  total_estimated_value_minor: number;
  weighted_value: string;
  weighted_value_minor: number;
  rows: LeadEntry[];
  top: LeadEntry[];
  due: LeadEntry[];
}

export interface ConversionStrategyRow {
  id: string;
  name: string;
  lead_count: number;
  open_count: number;
  won_count: number;
  lost_count: number;
  converted_count: number;
  conversion_rate_pct: number;
  linked_revenue: string;
  linked_revenue_minor: number;
  estimated_value: string;
  estimated_value_minor: number;
  average_deal: string;
  average_deal_minor: number;
}

export interface ConversionSummary {
  temple_id: string;
  total_leads: number;
  open_count: number;
  won_count: number;
  lost_count: number;
  closed_count: number;
  converted_count: number;
  conversion_rate_pct: number;
  win_rate_pct: number;
  linked_revenue: string;
  linked_revenue_minor: number;
  average_deal: string;
  average_deal_minor: number;
  open_weighted_value: string;
  open_weighted_value_minor: number;
  lost_value: string;
  lost_value_minor: number;
  by_strategy: ConversionStrategyRow[];
  recent: LeadEntry[];
  lost_notes: LeadEntry[];
}

export interface ExternalConnection {
  id: string;
  name: string;
  state: string;
  summary: string;
  next_action?: string;
  items?: Array<Record<string, string>>;
}

export interface ExternalSnapshot {
  connected_count: number;
  disabled_count?: number;
  connections: ExternalConnection[];
}

export interface ImportRow {
  row_number?: number;
  status: string;
  reason?: string;
  existing_id?: number;
  gbp?: string;
  source?: string;
}

export interface ImportResult {
  dry_run: boolean;
  ready_count?: number;
  imported_count: number;
  duplicate_count: number;
  skipped_count: number;
  rows: ImportRow[];
}

export interface DashboardPayload {
  version: string;
  status: StatusReport;
  income: IncomeEntry[];
  exceptions: JsonMap[];
  events: EventEntry[];
  opportunities: Opportunity[];
  top_opportunity: Opportunity | null;
  strategy_roi: StrategyRoi;
  report: ReportPayload;
  upgrades: string[];
  approvals: ApprovalSummary;
  leads: LeadPipelineSummary;
  conversions?: ConversionSummary;
  temples: TempleSummary;
  auth: AuthStatus;
  worker: WorkerStatus;
  config: ConfigPayload;
}

export interface AuthResponse {
  auth: AuthStatus;
}

export interface DashboardResponse {
  ok?: boolean;
  state: DashboardPayload;
  auth?: AuthStatus;
}
