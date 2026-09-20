/**
 * TypeScript types for Phase 12: LLM Reasoning & Grounded Explanations
 * 
 * These types match the Pydantic schemas in backend/app/schemas/llm.py
 */

/**
 * A citation linking answer content to repository evidence.
 */
export interface Citation {
  evidence_id: string;  // UUID
  file_path: string;
  start_line: number;
  end_line: number;
  symbol_name?: string;
  symbol_type?: string;
  excerpt: string;
}

/**
 * A grounded answer to a user question about a repository.
 */
export interface GroundedAnswer {
  question: string;
  answer: string;
  citations: Citation[];
  is_sufficient_evidence: boolean;
  confidence_note?: string;
  evidence_count: number;
  repository_id: string;  // UUID
  analysis_run_id?: string;  // UUID
}

/**
 * Request to ask a question about a repository.
 */
export interface AskRequest {
  question: string;
  top_k?: number;
  semantic_weight?: number;
  keyword_weight?: number;
  analysis_run_id?: string;
}

/**
 * Response from the Ask API endpoint.
 */
export interface AskResponse {
  answer: GroundedAnswer;
}

/**
 * Response when there is insufficient evidence to answer the question.
 */
export interface InsufficientEvidenceResponse {
  question: string;
  message: string;
  evidence_count: number;
  repository_id: string;  // UUID
}
