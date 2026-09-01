/**
 * Type definitions for repository data.
 */

export interface RepositoryRequest {
  url: string;
}

export interface RepositoryResponse {
  name: string;
  full_name: string;
  owner: string;
  description: string | null;
  url: string;
  default_branch: string;
  visibility: string;
  stars: number;
  forks: number;
  language: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface APIError {
  detail: string;
}

// Phase 2: Repository Analysis Types

export interface FileInfo {
  path: string;
  filename: string;
  extension: string;
  size_bytes: number;
  language: string | null;
  lines: number | null;
  is_sensitive: boolean;
}

// Phase 3: Static Code Analysis Types

export interface Symbol {
  name: string;
  type: string;
  language: string;
  file: string;
  start_line: number;
  end_line: number;
  parent: string | null;
}

export interface Import {
  file: string;
  source: string;
  names: string[];
  line: number;
}

export interface Call {
  file: string;
  caller: string;
  callee: string;
  line: number;
}

export interface AnalysisSummary {
  total_files: number;
  analyzed_files: number;
  skipped_files: number;
  failed_files: number;
  total_symbols: number;
  symbols_by_type: Record<string, number>;
  total_imports: number;
  total_calls: number;
}

export interface RepositoryAnalysisResponse {
  repository: string;
  status: string;
  total_files: number;
  total_size_bytes: number;
  languages: Record<string, number>;
  files: FileInfo[];
  files_returned: number;
  note: string | null;
  // Phase 3: Static analysis results
  analysis_summary?: AnalysisSummary;
  symbols?: Symbol[];
  imports?: Import[];
  calls?: Call[];
}
