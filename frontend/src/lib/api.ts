/**
 * Typed client for the Earnings Intelligence OS FastAPI backend.
 * The browser only ever talks to the API — never to Supabase directly.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * The admin token lives only in browser session storage. It is never
 * hard-coded, never read from a NEXT_PUBLIC_ variable, and only attached
 * to protected POST requests.
 */
const ADMIN_TOKEN_STORAGE_KEY = "eios-admin-token";
const ADMIN_TOKEN_CHANGE_EVENT = "eios-admin-token-change";

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY);
}

export function saveAdminToken(token: string): void {
  window.sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
  window.dispatchEvent(new Event(ADMIN_TOKEN_CHANGE_EVENT));
}

export function clearAdminToken(): void {
  window.sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
  window.dispatchEvent(new Event(ADMIN_TOKEN_CHANGE_EVENT));
}

/** Subscribe to token changes (for useSyncExternalStore). */
export function subscribeAdminToken(callback: () => void): () => void {
  window.addEventListener(ADMIN_TOKEN_CHANGE_EVENT, callback);
  return () => window.removeEventListener(ADMIN_TOKEN_CHANGE_EVENT, callback);
}

/**
 * Cold-start tracking. The Render free tier sleeps the API after inactivity,
 * so the first request of a session can take 30-60s while the dyno wakes. We
 * surface a non-blocking notice when any request stays in flight past a short
 * threshold instead of leaving the user staring at a spinner.
 */
const SLOW_REQUEST_MS = 3500;
const SLOW_CHANGE_EVENT = "eios-slow-change";
let inFlight = 0;
let isSlow = false;
let slowTimer: ReturnType<typeof setTimeout> | null = null;

function emitSlow(next: boolean) {
  if (next === isSlow) return;
  isSlow = next;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(SLOW_CHANGE_EVENT));
  }
}

function startRequest() {
  inFlight += 1;
  if (inFlight === 1 && slowTimer === null) {
    slowTimer = setTimeout(() => emitSlow(true), SLOW_REQUEST_MS);
  }
}

function endRequest() {
  inFlight = Math.max(0, inFlight - 1);
  if (inFlight === 0) {
    if (slowTimer !== null) {
      clearTimeout(slowTimer);
      slowTimer = null;
    }
    emitSlow(false);
  }
}

export function getApiIsSlow(): boolean {
  return isSlow;
}

export function subscribeApiSlow(callback: () => void): () => void {
  window.addEventListener(SLOW_CHANGE_EVENT, callback);
  return () => window.removeEventListener(SLOW_CHANGE_EVENT, callback);
}

export interface Filing {
  id: number;
  ticker: string;
  accession_number: string;
  form: string;
  filing_date: string | null;
  report_date: string | null;
  processing_status: string;
  sec_url: string | null;
  html_storage_path: string | null;
  text_storage_path: string | null;
  downloaded_at: string | null;
  parsed_at: string | null;
  chunked_at: string | null;
  processing_error: string | null;
}

export interface FilingsResponse {
  count: number;
  filings: Filing[];
}

export interface Company {
  ticker: string;
  company_name: string;
  cik: string;
  business_model: string | null;
}

export interface CompaniesResponse {
  count: number;
  companies: Company[];
}

export interface FilingDocument {
  id: number;
  document_type: string;
  filename: string;
  sec_url: string | null;
  html_storage_path: string | null;
  text_storage_path: string | null;
}

export interface FilingDetail {
  filing: Filing;
  documents: FilingDocument[];
  chunk_count: number;
}

export interface Brief {
  id: number;
  ticker: string;
  accession_number: string;
  version_number: number;
  markdown_content: string;
  storage_path: string;
  trusted_claim_count: number;
  factual_claim_count: number;
  interpretive_claim_count: number;
  generated_at: string;
}

export interface ProposedClaim {
  id: number;
  ticker: string;
  accession_number: string;
  document_key: string;
  theme: string;
  claim_text: string;
  supporting_excerpt: string;
  source_chunk_id: number;
  source_chunk_index: number;
  claim_type: string;
  confidence: string;
  review_status: string;
  created_at: string;
  reviewer_notes?: string | null;
  edited_claim_text?: string | null;
  reviewed_at?: string | null;
}

export interface ReviewQueueResponse {
  count: number;
  claims: ProposedClaim[];
}

export interface ExtractionReadyFiling {
  filing_id: number;
  ticker: string;
  accession_number: string;
  form: string;
  filing_date: string | null;
  exhibit_processing_status: string;
  earnings_release_document_id: number;
  filename: string | null;
  document_key: string | null;
  chunk_count: number;
  ready_for_extraction: boolean;
  claim_extraction_status: string;
  claim_extracted_at: string | null;
  claim_extraction_error: string | null;
  pending_grounded_claim_count: number;
  trusted_promoted_claim_count: number;
  latest_brief_version: number | null;
}

export interface ExtractionReadyResponse {
  count: number;
  filings: ExtractionReadyFiling[];
}

export interface BriefMeta {
  id: number;
  ticker: string;
  accession_number: string;
  version_number: number;
  storage_path: string;
  trusted_claim_count: number;
  factual_claim_count: number;
  interpretive_claim_count: number;
  generated_at: string;
}

export interface CompanyExtractionReadyRow {
  accession_number: string;
  form: string;
  filing_date: string | null;
  filename: string | null;
  document_key: string | null;
  chunk_count: number;
  claim_extraction_status: string;
}

export interface CompanyDetail {
  company: Company;
  filings_count: number;
  chunked_filings_count: number;
  extraction_ready_count: number;
  trusted_claim_count: number;
  latest_brief: BriefMeta | null;
  recent_filings: Filing[];
  extraction_ready: CompanyExtractionReadyRow[];
}

export interface OverviewCompanyRow {
  ticker: string;
  company_name: string;
  extraction_ready_count: number;
  trusted_claim_count: number;
  latest_brief_version: number | null;
  latest_filing_date: string | null;
}

export interface OverviewResponse {
  companies_count: number;
  total_filings_count: number;
  extraction_ready_count: number;
  pending_grounded_claim_count: number;
  trusted_claim_count: number;
  stored_brief_count: number;
  companies: OverviewCompanyRow[];
}

export interface ClaimExtractionResult {
  ticker: string;
  accession_number: string;
  document_key: string;
  proposed_claim_count: number;
  skipped_invalid_count: number;
  claim_extraction_status: string;
}

export interface PromotionResult {
  eligible_count: number;
  promoted_count: number;
  skipped_existing_count: number;
  approved_filings: string[];
  promoted_claims: {
    proposed_claim_id: number;
    ticker: string;
    theme: string;
    claim: string;
    source_chunk_id: number;
    document_key: string;
  }[];
}

export interface BriefGenerationResult {
  filing_id: number;
  ticker: string;
  accession_number: string;
  version_number: number;
  local_output_path: string;
  storage_path: string;
  trusted_claim_count: number;
  factual_claim_count: number;
  interpretive_claim_count: number;
}

// --- Quantitative research terminal (Bundle A) ---------------------------

export interface MetricPoint {
  fiscal_year: number;
  fiscal_quarter: string;
  period: string;
  value: number | null;
  unit?: string | null;
}

export interface MetricsResponse {
  ticker: string;
  metric_name: string | null;
  metric_count: number;
  period_count: number;
  periods: string[];
  metrics: Record<string, MetricPoint[]>;
  latest_period: string | null;
  latest_period_summary: Record<string, number | null>;
}

export interface PeerRow {
  ticker: string;
  company_name: string;
  business_model: string | null;
  revenue: number | null;
  yoy_revenue_growth: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  free_cash_flow_margin: number | null;
  rd_as_pct_of_revenue: number | null;
  ttm_revenue: number | null;
  ttm_operating_income: number | null;
  ttm_free_cash_flow: number | null;
  cash: number | null;
  total_debt: number | null;
  net_cash_debt: number | null;
  valuation_snapshot_date: string | null;
  share_price: number | null;
  market_cap: number | null;
  enterprise_value: number | null;
  debt_measure: string | null;
  valuation_notes: string | null;
  ev_to_ttm_revenue: number | null;
  ev_to_ttm_operating_income: number | null;
  price_to_ttm_fcf: number | null;
  free_cash_flow_yield: number | null;
}

export interface ComparabilityNote {
  ticker: string;
  business_model: string | null;
  debt_measure: string | null;
  notes: string | null;
}

export interface PeersResponse {
  count: number;
  peers: PeerRow[];
  valuation_is_live: boolean;
  valuation_snapshot_dates: string[];
  valuation_disclaimer: string;
  comparability_notes: ComparabilityNote[];
}

export interface TrendSeries {
  ticker: string;
  company_name: string;
  points: { fiscal_year: number; fiscal_quarter: string; period: string; value: number | null }[];
}

export interface PeerTrendsResponse {
  metric_name: string;
  series: TrendSeries[];
}

export interface ValuationSnapshot {
  id: number;
  ticker: string;
  share_price_date: string;
  share_price: number | null;
  shares_outstanding: number | null;
  shares_outstanding_source_date: string | null;
  market_cap: number | null;
  cash: number | null;
  total_debt: number | null;
  enterprise_value: number | null;
  debt_measure: string | null;
  source: string | null;
  manually_reviewed: string | null;
  notes: string | null;
  is_live: boolean;
}

export interface ValuationSnapshotsResponse {
  count: number;
  snapshots: ValuationSnapshot[];
  is_live: boolean;
  valuation_snapshot_dates: string[];
  valuation_disclaimer: string;
}

// --- Evidence Explorer & research reports (Bundle B1) --------------------

export interface EvidenceItem {
  qualitative_claim_id: number;
  ticker: string;
  theme: string | null;
  claim: string;
  supporting_excerpt: string | null;
  source_reference: string | null;
  source_chunk_id: number | null;
  document_key: string | null;
  factual_or_interpretive: string | null;
  confidence: string | null;
  human_reviewed: boolean | string | null;
  accession_number: string | null;
  filing_date: string | null;
  sec_url: string | null;
}

export interface EvidenceListResponse {
  count: number;
  evidence: EvidenceItem[];
}

export interface EvidenceDetail {
  claim: EvidenceItem & { qualitative_claim_id: number };
  chunk_text: string | null;
  chunk: Record<string, unknown> | null;
  document: FilingDocument | null;
  filing: {
    accession_number: string;
    form: string;
    filing_date: string | null;
    report_date: string | null;
    sec_url: string | null;
  } | null;
  sec_url: string | null;
}

export interface ReportMeta {
  id: number;
  ticker: string;
  accession_number: string | null;
  report_type: string;
  report_status: string;
  version_number: number;
  title: string;
  source_claim_count: number;
  source_metric_count: number;
  valuation_snapshot_date: string | null;
  generator_type: string;
  pdf_storage_path: string | null;
  generated_at: string;
  pdf_available?: boolean;
  source_report_id?: number | null;
}

export interface ReportsResponse {
  count: number;
  reports: ReportMeta[];
}

export interface ReportEvidenceLink {
  id: number;
  research_report_id: number;
  qualitative_claim_id: number | null;
  source_chunk_id: number | null;
  accession_number: string | null;
  document_key: string | null;
  section_name: string | null;
  supporting_excerpt: string | null;
}

export interface ReportDetail extends ReportMeta {
  markdown_content: string;
  html_content: string;
  evidence_links: ReportEvidenceLink[];
}

export interface ReportGenerateResult {
  report_id: number;
  ticker: string;
  accession_number: string | null;
  report_type: string;
  version_number: number;
  title: string;
  source_claim_count: number;
  source_metric_count: number;
  evidence_link_count: number;
  pdf_storage_path: string;
}

// --- Claude-assisted narrative review (Bundle B2.2) ----------------------

export interface ReportReviewItem {
  id: number;
  ticker: string;
  accession_number: string | null;
  report_type: string;
  report_status: string;
  version_number: number;
  title: string;
  imported_at: string | null;
  source_report_id: number | null;
  source_packet_hash: string | null;
  source_claim_count: number | null;
  source_metric_count: number | null;
  valuation_snapshot_date: string | null;
  generator_type: string;
  markdown_content: string;
  generated_at: string;
  evidence_link_count: number;
}

export interface ReportReviewQueueResponse {
  count: number;
  reports: ReportReviewItem[];
}

export interface ReviewedReport {
  id: number;
  ticker: string;
  accession_number: string | null;
  report_type: string;
  report_status: string;
  version_number: number;
  title: string;
  markdown_content: string;
  generator_type: string;
  source_report_id: number | null;
  source_packet_hash: string | null;
  imported_at: string | null;
  reviewed_at: string | null;
  reviewer_notes: string | null;
  rejection_reason: string | null;
  source_claim_count: number | null;
  source_metric_count: number | null;
  valuation_snapshot_date: string | null;
  generated_at: string;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };

  // Attach the admin token to protected (mutating) requests only;
  // GET endpoints are public and never need it.
  if (init?.method === "POST") {
    const token = getAdminToken();
    if (token) headers["X-Admin-Token"] = token;
  }

  let response: Response;
  startRequest();
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      `Cannot reach the API at ${API_BASE_URL}. Is the backend running?`,
    );
  } finally {
    endRequest();
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new ApiError(401, "Admin token missing or invalid.");
    }
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail) detail = JSON.stringify(body.detail);
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getCompanies() {
    return request<CompaniesResponse>("/companies");
  },

  getCompany(ticker: string) {
    return request<CompanyDetail>(
      `/companies/${encodeURIComponent(ticker)}`,
    );
  },

  getOverview() {
    return request<OverviewResponse>("/overview");
  },

  /**
   * The only GET that carries the admin token — used by the Admin Access
   * panel to verify a saved token without performing any mutation.
   */
  validateAdminToken() {
    const token = getAdminToken();
    return request<{ status: string }>("/admin/validate", {
      headers: token ? { "X-Admin-Token": token } : {},
    });
  },

  getFilings(params?: { ticker?: string; status?: string; limit?: number }) {
    const search = new URLSearchParams();
    if (params?.ticker) search.set("ticker", params.ticker);
    if (params?.status) search.set("status", params.status);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return request<FilingsResponse>(`/filings${qs ? `?${qs}` : ""}`);
  },

  getFiling(accessionNumber: string) {
    return request<FilingDetail>(
      `/filings/${encodeURIComponent(accessionNumber)}`,
    );
  },

  getLatestBrief(ticker: string) {
    return request<Brief>(`/briefs/latest/${encodeURIComponent(ticker)}`);
  },

  getReviewQueue() {
    return request<ReviewQueueResponse>("/review-queue");
  },

  getExtractionReady() {
    return request<ExtractionReadyResponse>("/extraction-ready");
  },

  extractClaims(accessionNumber: string, maxClaims = 5) {
    return request<ClaimExtractionResult>(
      `/extraction-ready/${encodeURIComponent(accessionNumber)}/extract`,
      {
        method: "POST",
        body: JSON.stringify({ max_claims: maxClaims }),
      },
    );
  },

  approveClaim(claimId: number, reviewerNotes?: string) {
    return request<ProposedClaim>(`/review-queue/${claimId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reviewer_notes: reviewerNotes || null }),
    });
  },

  editClaim(claimId: number, editedClaimText: string, reviewerNotes?: string) {
    return request<ProposedClaim>(`/review-queue/${claimId}/edit`, {
      method: "POST",
      body: JSON.stringify({
        edited_claim_text: editedClaimText,
        reviewer_notes: reviewerNotes || null,
      }),
    });
  },

  rejectClaim(claimId: number, reviewerNotes?: string) {
    return request<ProposedClaim>(`/review-queue/${claimId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reviewer_notes: reviewerNotes || null }),
    });
  },

  promoteClaims(ticker: string, accessionNumber: string) {
    return request<PromotionResult>("/claims/promote", {
      method: "POST",
      body: JSON.stringify({ ticker, accession_number: accessionNumber }),
    });
  },

  generateBrief(ticker: string, accessionNumber: string) {
    return request<BriefGenerationResult>("/briefs/generate", {
      method: "POST",
      body: JSON.stringify({ ticker, accession_number: accessionNumber }),
    });
  },

  // --- Quantitative research terminal (public reads) --------------------

  getMetrics(ticker: string, metricName?: string) {
    const qs = metricName
      ? `?metric_name=${encodeURIComponent(metricName)}`
      : "";
    return request<MetricsResponse>(
      `/metrics/${encodeURIComponent(ticker)}${qs}`,
    );
  },

  getPeers() {
    return request<PeersResponse>("/peers");
  },

  getPeerTrends(metricName: string, params?: { ticker?: string; limit?: number }) {
    const search = new URLSearchParams({ metric_name: metricName });
    if (params?.ticker) search.set("ticker", params.ticker);
    if (params?.limit) search.set("limit", String(params.limit));
    return request<PeerTrendsResponse>(`/peers/trends?${search.toString()}`);
  },

  getValuationSnapshots() {
    return request<ValuationSnapshotsResponse>("/valuation-snapshots");
  },

  // --- Evidence Explorer & research reports -----------------------------

  getEvidence(params?: {
    ticker?: string;
    accession_number?: string;
    theme?: string;
    claim_type?: string;
    confidence?: string;
    document_key?: string;
    limit?: number;
  }) {
    const search = new URLSearchParams();
    if (params?.ticker) search.set("ticker", params.ticker);
    if (params?.accession_number)
      search.set("accession_number", params.accession_number);
    if (params?.theme) search.set("theme", params.theme);
    if (params?.claim_type) search.set("claim_type", params.claim_type);
    if (params?.confidence) search.set("confidence", params.confidence);
    if (params?.document_key) search.set("document_key", params.document_key);
    if (params?.limit) search.set("limit", String(params.limit));
    const qs = search.toString();
    return request<EvidenceListResponse>(`/evidence${qs ? `?${qs}` : ""}`);
  },

  getEvidenceDetail(claimId: number) {
    return request<EvidenceDetail>(`/evidence/${claimId}`);
  },

  /**
   * Admin-only: correct the wording and/or excerpt of a promoted trusted
   * claim. A corrected excerpt must be a literal quote from the claim's
   * source chunk — the backend re-validates the grounding rule.
   */
  editEvidenceClaim(
    claimId: number,
    changes: {
      editedClaimText?: string;
      editedSupportingExcerpt?: string;
      reviewerNotes?: string;
    },
  ) {
    return request<{
      qualitative_claim_id: number;
      ticker: string;
      theme: string | null;
      previous_claim: string;
      claim: string;
      previous_supporting_excerpt: string | null;
      supporting_excerpt: string | null;
      source_reference: string | null;
      corrected_at: string;
    }>(`/evidence/${claimId}/edit`, {
      method: "POST",
      body: JSON.stringify({
        edited_claim_text: changes.editedClaimText || null,
        edited_supporting_excerpt: changes.editedSupportingExcerpt || null,
        reviewer_notes: changes.reviewerNotes || null,
      }),
    });
  },

  getReports(params?: {
    ticker?: string;
    report_type?: string;
    report_status?: string;
  }) {
    const search = new URLSearchParams();
    if (params?.ticker) search.set("ticker", params.ticker);
    if (params?.report_type) search.set("report_type", params.report_type);
    if (params?.report_status) search.set("report_status", params.report_status);
    const qs = search.toString();
    return request<ReportsResponse>(`/reports${qs ? `?${qs}` : ""}`);
  },

  getLatestReport(ticker: string, reportType?: string) {
    const qs = reportType
      ? `?report_type=${encodeURIComponent(reportType)}`
      : "";
    return request<ReportDetail>(
      `/reports/latest/${encodeURIComponent(ticker)}${qs}`,
    );
  },

  getReport(reportId: number) {
    return request<ReportDetail>(`/reports/${reportId}`);
  },

  /** Direct backend route that 307-redirects to a short-lived signed PDF URL. */
  reportPdfUrl(reportId: number) {
    return `${API_BASE_URL}/reports/${reportId}/pdf`;
  },

  generateReport(body: {
    ticker: string;
    accession_number?: string | null;
    report_type?: string;
  }) {
    return request<ReportGenerateResult>("/reports/generate", {
      method: "POST",
      body: JSON.stringify({
        ticker: body.ticker,
        accession_number: body.accession_number ?? null,
        report_type: body.report_type ?? "earnings_update",
      }),
    });
  },

  // --- Claude-assisted narrative review (admin) -------------------------

  /** Admin-only: the review queue is a GET that carries the admin token. */
  getReportReviewQueue() {
    const token = getAdminToken();
    return request<ReportReviewQueueResponse>("/reports/review-queue", {
      headers: token ? { "X-Admin-Token": token } : {},
    });
  },

  approveReport(reportId: number, reviewerNotes?: string) {
    return request<ReviewedReport>(`/reports/${reportId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reviewer_notes: reviewerNotes || null }),
    });
  },

  editAndApproveReport(
    reportId: number,
    editedMarkdownContent: string,
    reviewerNotes?: string,
  ) {
    return request<ReviewedReport>(`/reports/${reportId}/edit-and-approve`, {
      method: "POST",
      body: JSON.stringify({
        edited_markdown_content: editedMarkdownContent,
        reviewer_notes: reviewerNotes || null,
      }),
    });
  },

  rejectReport(reportId: number, rejectionReason: string, reviewerNotes?: string) {
    return request<ReviewedReport>(`/reports/${reportId}/reject`, {
      method: "POST",
      body: JSON.stringify({
        rejection_reason: rejectionReason,
        reviewer_notes: reviewerNotes || null,
      }),
    });
  },
};
