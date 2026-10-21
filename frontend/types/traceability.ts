/**
 * TypeScript types for Phase 22: Test-to-Code Traceability & Coverage Intelligence
 * 
 * Matches backend schemas from backend/app/api/traceability.py
 */

// Reuse AffectedTest from Phase 19 test intelligence
export interface AffectedTest {
  test_file: string;
  test_name: string | null;
  coverage_type: string;
  confidence: string;
  evidence: string[];
  changed_symbols: string[];
}

export interface SourceTraceabilityResponse {
  repository_id: string;
  source_file: string;
  analysis_run_id: string | null;
  total_related_tests: number;
  related_tests: AffectedTest[];
}

export interface SymbolTraceabilityResponse {
  repository_id: string;
  symbol_name: string;
  file_path: string | null;
  analysis_run_id: string | null;
  total_related_tests: number;
  related_tests: AffectedTest[];
}

export interface RelatedSourceFile {
  source_file: string;
  relationship_type: string;
  confidence: string;
  evidence: string[];
  imported_symbols: string[];
}

export interface TestTraceabilityResponse {
  repository_id: string;
  test_file: string;
  analysis_run_id: string | null;
  total_related_sources: number;
  related_sources: RelatedSourceFile[];
}

// Request parameters for traceability queries
export interface SourceTraceabilityRequest {
  source_file: string;
  analysis_run_id?: string | null;
}

export interface SymbolTraceabilityRequest {
  symbol_name: string;
  file_path?: string | null;
  analysis_run_id?: string | null;
}

export interface TestTraceabilityRequest {
  test_file: string;
  analysis_run_id?: string | null;
}
