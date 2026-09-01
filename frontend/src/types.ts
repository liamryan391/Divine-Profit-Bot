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

export interface WorkerCycle {
  id: number;
  worker_name: string;
  trigger: string;
  status: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  commands: { total: number; succeeded: number; failed: number };
  rules: { evaluated: number; triggered: number; blocked: number };
  approvals: { required: number; pending: number };
  failure_count: number;
  error_summary?: string;
  outcome?: JsonMap;
}

export interface WorkerSignal {
  ok: boolean;
  state: string;
  detail: string;
}

export interface WorkerStatus {
  worker_name?: string;
  state: string;
  health?: string;
  live?: boolean;
  ready?: boolean;
  stale?: boolean;
  liveness?: WorkerSignal;
  readiness?: WorkerSignal;
  last_seen_at?: string | null;
  age_seconds: number | null;
  detail?: string;
  stale_after_seconds?: number;
  latest_cycle?: WorkerCycle | null;
  latest_worker_cycle?: WorkerCycle | null;
  recent_cycles?: WorkerCycle[];
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
  receivable_id?: number | null;
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
  generated?: boolean;
  period: {
    start: string;
    end: string;
  };
}

export interface DashboardSnapshotMetadata {
  generated_at: string;
  duration_ms: number;
  budget_ms: number;
  within_budget: boolean;
}

export interface ApprovalAction {
  id: number;
  receivable_id?: number | null;
  follow_up_event_id?: number | null;
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
  lost_value?: string;
  lost_value_minor?: number;
  strategy_metrics?: Record<
    string,
    {
      open_count: number;
      due_count: number;
      open_weighted_value_minor: number;
      lost_value_minor: number;
    }
  >;
  pagination?: {
    limit: number;
    offset: number;
    returned: number;
    total: number;
    has_more: boolean;
    has_previous: boolean;
    next_offset: number | null;
    previous_offset: number | null;
  };
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

export interface ReceivableEntry {
  id: number;
  temple_id: string;
  lead_id?: number | null;
  source_income_id?: number | null;
  active_reminder_id?: number | null;
  active_reminder_status?: string | null;
  client: string;
  reference: string;
  description?: string;
  amount_minor: number;
  currency: string;
  gbp_minor: number;
  paid_gbp_minor: number;
  outstanding_gbp_minor: number;
  amount: string;
  gbp_value: string;
  paid: string;
  outstanding: string;
  paid_pct: number;
  issued_on: string;
  due_on: string;
  status: string;
  state: string;
  state_label: string;
  days_until_due: number;
  already_counted: boolean;
  can_record_payment: boolean;
  can_remind: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ReceivablePayment {
  id: number;
  receivable_id: number;
  amount_minor: number;
  currency: string;
  gbp_minor: number;
  counted_income_id?: number | null;
  payment_reference?: string;
  occurred_on: string;
  note?: string;
  reference: string;
  client: string;
  amount: string;
  counted: string;
  counted_as_income: boolean;
}

export interface ReceivablesSummary {
  temple_id: string;
  total_count: number;
  active_count: number;
  overdue_count: number;
  due_soon_count: number;
  partial_count: number;
  paid_count: number;
  void_count: number;
  total_value: string;
  total_value_minor: number;
  collected: string;
  collected_minor: number;
  outstanding: string;
  outstanding_minor: number;
  overdue: string;
  overdue_minor: number;
  filter: string;
  returned_count: number;
  rows: ReceivableEntry[];
  at_risk: ReceivableEntry[];
  recent_payments: ReceivablePayment[];
  policy: string[];
}

export interface FollowUpCadence {
  id: number;
  temple_id: string;
  name: string;
  enabled: boolean;
  due_soon_days: number[];
  overdue_days: number[];
  due_soon_display: string;
  overdue_display: string;
  minimum_gap_days: number;
  max_reminders: number;
  stop_after_overdue_days: number;
  created_at: string;
  updated_at: string;
}

export interface ClientContactState {
  id: number;
  temple_id: string;
  client_key: string;
  client: string;
  status: string;
  effective_status: string;
  status_label: string;
  suppress_until: string;
  reason: string;
  last_contact_at: string;
  last_outcome: string;
  suppressed: boolean;
  created_at: string;
  updated_at: string;
}

export interface FollowUpEvent {
  id: number;
  temple_id: string;
  receivable_id: number;
  cadence_id?: number | null;
  approval_id?: number | null;
  source: string;
  cadence_kind: string;
  offset_days: number;
  scheduled_for: string;
  client_key: string;
  client: string;
  reference: string;
  due_on: string;
  status: string;
  status_label: string;
  suppression_reason: string;
  outcome: string;
  outcome_label: string;
  outcome_note: string;
  schedule_label: string;
  outstanding: string;
  outstanding_gbp_minor: number;
  approval_required: boolean;
  can_record_outcome: boolean;
  drafted_at: string;
  reviewed_at: string;
  outcome_at: string;
  created_at: string;
  updated_at: string;
}

export interface FollowUpScheduleItem {
  receivable_id: number;
  reference: string;
  client: string;
  outstanding: string;
  outstanding_gbp_minor: number;
  due_on: string;
  cadence_kind: string;
  offset_days: number;
  scheduled_for: string;
  days_until: number;
  status: string;
  status_label: string;
  suppression_reason: string;
}

export interface FollowUpMetrics {
  completed_reminders: number;
  response_count: number;
  response_rate_pct: number;
  payment_promised_count: number;
  partial_payment_count: number;
  paid_count: number;
  no_response_count: number;
  collected_after_reminder: string;
  collected_after_reminder_minor: number;
  assisted_paid_receivables: number;
  average_collection_days: number;
  average_overdue_days: number;
  outcomes: Record<string, number>;
}

export interface FollowUpSummary {
  temple_id: string;
  cadence: FollowUpCadence;
  counts: Record<string, number>;
  due_count: number;
  suppressed_client_count: number;
  upcoming: FollowUpScheduleItem[];
  recent: FollowUpEvent[];
  client_states: ClientContactState[];
  metrics: FollowUpMetrics;
  policy: string[];
}

export interface ReconciliationCandidate {
  receivable_id: number;
  reference: string;
  client: string;
  currency: string;
  outstanding: string;
  outstanding_gbp_minor: number;
  already_counted: boolean;
  score: number;
  reasons: string[];
  compatible: boolean;
}

export interface ReconciliationTransaction {
  id: number;
  temple_id: string;
  batch_id: number;
  provider: string;
  external_reference: string;
  amount_minor: number;
  currency: string;
  gbp_minor: number;
  amount: string;
  gbp_value: string;
  occurred_on: string;
  payer: string;
  description: string;
  status: string;
  status_label: string;
  suggested_receivable_id?: number | null;
  match_confidence: number;
  match_label: string;
  match_label_display: string;
  match_reasons: string[];
  candidates: ReconciliationCandidate[];
  matched_receivable_id?: number | null;
  matched_payment_id?: number | null;
  income_treatment: string;
  decision_note?: string;
  ambiguous: boolean;
  can_decide: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReconciliationDecision {
  id: number;
  reconciliation_transaction_id: number;
  action: string;
  action_label: string;
  receivable_id?: number | null;
  payment_id?: number | null;
  count_as_income: boolean;
  note: string;
  provider: string;
  external_reference: string;
  gbp_minor: number;
  receivable_reference?: string | null;
  receivable_client?: string | null;
  created_at: string;
  evidence: JsonMap;
}

export interface ReconciliationBatch {
  id: number;
  provider: string;
  filename: string;
  repeated_of_batch_id?: number | null;
  row_count: number;
  imported_count: number;
  duplicate_count: number;
  skipped_count: number;
  created_at: string;
}

export interface ReconciliationReceivableOption {
  id: number;
  reference: string;
  client: string;
  currency: string;
  outstanding: string;
  outstanding_gbp_minor: number;
  already_counted: boolean;
}

export interface ReconciliationSummary {
  temple_id: string;
  total_count: number;
  unmatched_count: number;
  suggested_count: number;
  matched_count: number;
  ignored_count: number;
  ambiguous_count: number;
  review_count: number;
  imported: string;
  imported_minor: number;
  awaiting_review: string;
  awaiting_review_minor: number;
  matched: string;
  matched_minor: number;
  filter: string;
  returned_count: number;
  rows: ReconciliationTransaction[];
  recent_decisions: ReconciliationDecision[];
  recent_batches: ReconciliationBatch[];
  receivable_options: ReconciliationReceivableOption[];
  policy: string[];
}

export interface ReconciliationImportRow {
  row_number?: number;
  id?: number;
  status: string;
  suggested_status?: string;
  reason?: string;
  existing_id?: number;
  amount?: string;
  gbp_value?: string;
  payer?: string;
  match_confidence?: number;
  match_label?: string;
  suggested_receivable_id?: number | null;
}

export interface ReconciliationImportResult {
  provider: string;
  filename: string;
  dry_run: boolean;
  batch_id?: number | null;
  row_count: number;
  ready_count: number;
  imported_count: number;
  duplicate_count: number;
  skipped_count: number;
  rows: ReconciliationImportRow[];
}

export interface RevenueRuleEvaluation {
  triggered: boolean;
  decision: string;
  severity: string;
  metric_value: number;
  metric_value_display: string;
  threshold_display: string;
  operator_label: string;
  distance: number;
  message: string;
}

export interface RevenueRuleEntry {
  id: number;
  temple_id: string;
  name: string;
  strategy: string;
  strategy_label: string;
  rule_type: string;
  rule_type_label: string;
  metric: string;
  metric_label: string;
  operator: string;
  threshold_value: number;
  threshold_display: string;
  action: string;
  approval_required: boolean;
  status: string;
  status_label: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  evaluation: RevenueRuleEvaluation;
}

export interface RevenueRulesSummary {
  temple_id: string;
  total_count: number;
  active_count: number;
  paused_count: number;
  triggered_count: number;
  approval_required_count: number;
  blocked_count: number;
  apply_count: number;
  rows: RevenueRuleEntry[];
  top_actions: RevenueRuleEntry[];
  recent_runs: RevenueRuleRun[];
  policy: string[];
}

export interface RevenueRuleRun {
  id: number;
  rule_id: number;
  rule_name: string;
  strategy: string;
  decision: string;
  triggered: boolean;
  metric: string;
  metric_label: string;
  metric_value: number;
  metric_value_display: string;
  threshold_value: number;
  threshold_display: string;
  message: string;
  created_at: string;
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
  snapshot?: DashboardSnapshotMetadata;
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
  receivables: ReceivablesSummary;
  reconciliation?: ReconciliationSummary;
  follow_ups?: FollowUpSummary;
  revenue_rules?: RevenueRulesSummary;
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
