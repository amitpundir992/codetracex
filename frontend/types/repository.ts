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

export interface RepositoryAnalysisResponse {
  repository: string;
  status: string;
  total_files: number;
  total_size_bytes: number;
  languages: Record<string, number>;
  files: FileInfo[];
  files_returned: number;
  note: string | null;
}
