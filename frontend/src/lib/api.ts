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
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      `Cannot reach the API at ${API_BASE_URL}. Is the backend running?`,
    );
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
};
