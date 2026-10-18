/**
 * TypeScript types for Phase 20: Test Results & Failure Intelligence
 * 
 * Matches backend schemas from backend/app/schemas/test_results.py
 */

export interface TestResultImportRequest {
  report_content: string;
  format_hint?: string;
  commit_sha?: string | null;
  analysis_run_id?: string | null;
}

export interface TestResultImportResponse {
  test_run_id: string;
  repository_id: string;
  status: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  error_tests: number;
  source_format: string;
  was_duplicate: boolean;
}

export interface TestRunSummary {
  id: string;
  repository_id: string;
  commit_sha: string | null;
  source_format: string;
  status: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  error_tests: number;
  total_duration_ms: number | null;
  imported_at: string;
}

export interface TestRunListResponse {
  repository_id: string;
  total_count: number;
  limit: number;
  offset: number;
  test_runs: TestRunSummary[];
}

export interface TestCaseDetail {
  id: string;
  suite_name: string;
  test_name: string;
  class_name: string | null;
  full_name: string;
  outcome: string;
  duration_ms: number | null;
  failure_message: string | null;
  failure_type: string | null;
  failure_stacktrace: string | null;
  failure_classification: string | null;
  classification_confidence: number | null;
  classification_evidence: string | null;
}

export interface TestRunDetailResponse {
  id: string;
  repository_id: string;
  commit_sha: string | null;
  analysis_run_id: string | null;
  source_format: string;
  status: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  error_tests: number;
  total_duration_ms: number | null;
  imported_at: string;
  processed_at: string | null;
  test_cases: TestCaseDetail[];
}

export interface FailureCorrelation {
  test_case_id: string;
  test_name: string;
  correlation_type: string;
  confidence: string;
  changed_files: string[];
  changed_symbols: string[];
  evidence: string[];
}

export interface HistoricalTrend {
  test_name: string;
  trend_type: string;
  description: string;
  runs_analyzed: number;
  evidence: string[];
  confidence: string;
}

export interface TestFailuresResponse {
  test_run_id: string;
  repository_id: string;
  total_failures: number;
  failed_tests: TestCaseDetail[];
  correlations: FailureCorrelation[];
  trends: HistoricalTrend[];
}

export interface FailureExplainRequest {
  test_case_id: string;
  include_correlations?: boolean;
  include_trends?: boolean;
}

export interface FailureExplainResponse {
  test_name: string;
  failure_summary: string;
  potential_causes: string;
  investigation_steps: string;
  related_changes: string;
  uncertainty: string;
}
