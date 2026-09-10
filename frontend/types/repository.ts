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

// Phase 7: API Endpoints Types

export interface ApiEndpointSummary {
  id: string;
  method: string;
  path: string;
  framework: string;
  handler_name: string | null;
  start_line: number | null;
  end_line: number | null;
  file_path: string;
}

export interface SymbolInfo {
  id: string;
  name: string;
  type: string;
  file_path: string;
  start_line: number;
  end_line: number;
}

export interface ApiEndpointDetail {
  id: string;
  method: string;
  path: string;
  framework: string;
  handler_name: string | null;
  start_line: number | null;
  end_line: number | null;
  repository_id: string;
  analysis_run_id: string;
  file_id: string;
  file_path: string;
  symbol_id: string | null;
  handler_symbol: SymbolInfo | null;
  created_at: string;
}

export interface PaginatedApiEndpointsResponse {
  items: ApiEndpointSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DependencyNode {
  id: string;
  name: string;
  type: string;
  file_path: string | null;
}

export interface ApiEndpointDependencies {
  endpoint_id: string;
  method: string;
  path: string;
  handler_name: string | null;
  dependencies: DependencyNode[];
  callers: DependencyNode[];
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
  // Phase 4: Database persistence IDs
  repository_id?: string;
  analysis_run_id?: string;
}

// Phase 5: Graph Query Types

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  file?: string;
  language?: string;
}

export interface GraphEdge {
  type: string;
  source: GraphNode;
  target: GraphNode;
  line_number?: number;
}

export interface SymbolCallersResponse {
  symbol_id: string;
  symbol_name: string;
  depth: number;
  callers: GraphEdge[];
  total_callers: number;
}

export interface SymbolCalleesResponse {
  symbol_id: string;
  symbol_name: string;
  depth: number;
  callees: GraphEdge[];
  total_callees: number;
}

export interface SymbolDependenciesResponse {
  symbol_id: string;
  symbol_name: string;
  depth: number;
  calls: GraphEdge[];
  imports: GraphEdge[];
  total_dependencies: number;
}

export interface SymbolDependentsResponse {
  symbol_id: string;
  symbol_name: string;
  depth: number;
  callers: GraphEdge[];
  imported_by: GraphEdge[];
  total_dependents: number;
}

export interface FileDependenciesResponse {
  file_id: string;
  file_path: string;
  imports: GraphEdge[];
  total_dependencies: number;
}

export interface FileDependentsResponse {
  file_id: string;
  file_path: string;
  imported_by: GraphEdge[];
  total_dependents: number;
}

export interface ImpactAnalysisResponse {
  target: GraphNode;
  direct_callers: GraphNode[];
  indirect_dependents: GraphNode[];
  total_dependents: number;
  depth_map: Record<string, number>;
  max_depth: number;
}

// Phase 6: Git History Types

export interface Commit {
  id: string;
  repository_id: string;
  commit_hash: string;
  author_name: string;
  author_email: string;
  commit_message: string;
  committed_at: string;
  parent_hashes: string[];
  created_at: string;
}

export interface CommitFileChange {
  id: string;
  commit_id: string;
  file_id: string | null;
  path: string;
  change_type: 'added' | 'modified' | 'deleted' | 'renamed';
  additions: number;
  deletions: number;
  old_path: string | null;
  new_path: string | null;
  created_at: string;
}

export interface CommitSummary {
  id: string;
  commit_hash: string;
  commit_message: string;
  author_name: string;
  author_email: string;
  committed_at: string;
  file_change_count: number;
}

export interface CommitDetail {
  id: string;
  commit_hash: string;
  commit_message: string;
  author_name: string;
  author_email: string;
  committed_at: string;
  parent_hashes: string[];
  changes: CommitFileChange[];
}

export interface PaginatedCommitResponse {
  commits: CommitSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FileHistoryEntry {
  commit_id: string;
  commit_hash: string;
  commit_message: string;
  author_name: string;
  author_email: string;
  committed_at: string;
  change_type: 'added' | 'modified' | 'deleted' | 'renamed';
  additions: number;
  deletions: number;
  old_path: string | null;
  new_path: string | null;
}

export interface FileHistoryResponse {
  file_id: string;
  file_path: string;
  history: FileHistoryEntry[];
  total_commits: number;
}

export interface CoChangeFile {
  file_id: string;
  file_path: string;
  shared_commits: number;
}

export interface CoChangeResponse {
  file_id: string;
  file_path: string;
  co_changes: CoChangeFile[];
  total_co_changes: number;
}
