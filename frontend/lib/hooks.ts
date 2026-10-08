/**
 * React Query hooks for CodeTraceX API endpoints.
 * 
 * Phase 17: Unified Developer Workspace UI
 * 
 * Provides type-safe hooks for:
 * - Repository retrieval
 * - File and symbol exploration
 * - Investigation (Phase 16)
 * - Impact analysis (Phase 13)
 * - Background jobs (Phase 14)
 * - Dependency graphs
 * - Workflows
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface RepositorySummary {
  id: string;
  owner: string;
  name: string;
  full_name: string;
  github_url: string;
  default_branch: string | null;
  description: string | null;
  language: string | null;
  stars: number | null;
  created_at: string;
  updated_at: string;
}

export interface AnalysisSummary {
  id: string;
  repository_id: string;
  status: string;
  total_files: number | null;
  analyzed_files: number | null;
  total_symbols: number | null;
  total_imports: number | null;
  total_calls: number | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

export interface RepositoryFile {
  id: string;
  path: string;
  language: string | null;
  size_bytes: number | null;
  line_count: number | null;
  is_sensitive: boolean;
}

export interface RepositoryFileContent {
  path: string;
  language: string | null;
  content: string;
}

export interface BackgroundJob {
  job_id: string | null;
  analysis_run_id: string;
  repository_id: string;
  repository_name: string;
  status: string;
  progress: number | null;
  current_stage: string | null;
  total_files: number;
  analyzed_files: number;
  total_symbols: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface StartedAnalysis {
  job_id: string;
  analysis_run_id: string;
  repository_id: string;
  status: string;
}

export interface InvestigationEvidence {
  evidence_id?: string;
  evidence_type?: string;
  retrieval_source?: string;
  content?: string;
  file_path?: string | null;
  start_line?: number | null;
  end_line?: number | null;
  symbol_name?: string | null;
  symbol_type?: string | null;
  retrieval_score?: number | null;
  [key: string]: unknown;
}

export interface InvestigationResponse {
  question: string;
  detected_intent?: string;
  answer: string;
  claims?: Array<{
    claim_text: string;
    certainty: string;
    evidence_ids?: string[];
    reasoning?: string | null;
  }>;
  evidence?: InvestigationEvidence[];
  limitations?: string[];
  follow_up_questions?: Array<{
    question: string;
    rationale?: string | null;
    related_evidence_ids?: string[];
  }>;
  conversation_context?: InvestigationRequest['conversation_context'];
}

export class ApiRequestError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

async function requestError(response: Response, fallback: string): Promise<Error> {
  const safeMessage = response.status === 403
    ? 'This file is unavailable.'
    : response.status === 404
      ? 'The requested repository or resource was not found.'
      : response.status === 413
        ? 'This file is too large to display.'
        : fallback;

  return new ApiRequestError(safeMessage, response.status);
}

// ============================================================================
// Repository Hooks
// ============================================================================

export function useRepository(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}`);
      if (!response.ok) throw await requestError(response, 'Unable to load repository.');
      return response.json() as Promise<RepositorySummary>;
    },
    enabled: !!repositoryId,
  });
}

export function useRepositories() {
  return useQuery({
    queryKey: ['repositories'],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/repositories/`);
      if (!response.ok) throw await requestError(response, 'Unable to load repositories.');
      return response.json() as Promise<RepositorySummary[]>;
    },
  });
}

export function useLatestAnalysis(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'latest-analysis'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/analysis/latest`
      );
      if (response.status === 404) return null;
      if (!response.ok) throw await requestError(response, 'Unable to load analysis information.');
      return response.json() as Promise<AnalysisSummary>;
    },
    enabled: !!repositoryId,
  });
}

export function useAnalysisRuns(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'analyses'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/analysis`
      );
      if (!response.ok) throw await requestError(response, 'Unable to load analysis history.');
      return response.json() as Promise<AnalysisSummary[]>;
    },
    enabled: !!repositoryId,
  });
}

// ============================================================================
// File Hooks
// ============================================================================

export function useFiles(repositoryId: string, analysisRunId?: string, search?: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'files', analysisRunId, search],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: '10000' });
      if (analysisRunId) params.set('analysis_run_id', analysisRunId);
      if (search) params.set('search', search);
      const url = `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/files?${params}`;
      const response = await fetch(url);
      if (!response.ok) throw await requestError(response, 'Unable to load repository files.');
      return response.json() as Promise<RepositoryFile[]>;
    },
    enabled: !!repositoryId,
  });
}

export function useFile(repositoryId: string, fileId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'file', fileId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/files/${encodeURIComponent(fileId)}/content`
      );
      if (!response.ok) throw await requestError(response, 'Unable to load this file.');
      return response.json() as Promise<RepositoryFileContent>;
    },
    enabled: !!repositoryId && !!fileId,
  });
}

// ============================================================================
// Symbol Hooks
// ============================================================================

export function useSymbols(repositoryId: string, filters?: {
  name?: string;
  symbol_type?: string;
  language?: string;
  file_path?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'symbols', filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.name) params.append('name', filters.name);
      if (filters?.symbol_type) params.append('symbol_type', filters.symbol_type);
      if (filters?.language) params.append('language', filters.language);
      if (filters?.limit) params.append('limit', filters.limit.toString());
      
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/symbols?${params}`
      );
      if (!response.ok) throw await requestError(response, 'Unable to load repository symbols.');
      const symbols = await response.json() as Array<{ file: string }>;
      return filters?.file_path
        ? symbols.filter((symbol) => symbol.file === filters.file_path)
        : symbols;
    },
    enabled: !!repositoryId,
  });
}

export function useSymbol(repositoryId: string, symbolId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'symbol', symbolId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/retrieval/repositories/${repositoryId}/symbols/${symbolId}`
      );
      if (!response.ok) throw new Error('Failed to fetch symbol');
      return response.json();
    },
    enabled: !!repositoryId && !!symbolId,
  });
}

// ============================================================================
// API Endpoints Hooks
// ============================================================================

export function useApiEndpoints(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'api-endpoints'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/endpoints`
      );
      if (!response.ok) throw await requestError(response, 'Unable to load API endpoints.');
      return response.json();
    },
    enabled: !!repositoryId,
  });
}

// ============================================================================
// Dependency Graph Hooks
// ============================================================================

export function useSymbolCallers(repositoryId: string, symbolId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'symbol', symbolId, 'callers'],
    queryFn: () => api.getSymbolCallers(repositoryId, symbolId),
    enabled: !!repositoryId && !!symbolId,
  });
}

export function useSymbolCallees(repositoryId: string, symbolId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'symbol', symbolId, 'callees'],
    queryFn: () => api.getSymbolCallees(repositoryId, symbolId),
    enabled: !!repositoryId && !!symbolId,
  });
}

export function useDependencyGraph(repositoryId: string, symbolId: string, depth: number = 2) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'symbol', symbolId, 'graph', depth],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/retrieval/repositories/${repositoryId}/symbols/${symbolId}/graph?depth=${depth}`
      );
      if (!response.ok) throw new Error('Failed to fetch dependency graph');
      return response.json();
    },
    enabled: !!repositoryId && !!symbolId,
  });
}

// ============================================================================
// Workflow Hooks
// ============================================================================

export function useWorkflows(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'workflows'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/workflows/repositories/${repositoryId}/workflows`
      );
      if (!response.ok) throw new Error('Failed to fetch workflows');
      return response.json();
    },
    enabled: !!repositoryId,
  });
}

export function useEndpointWorkflow(repositoryId: string, endpointId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'endpoint', endpointId, 'workflow'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/workflows/repositories/${repositoryId}/endpoints/${endpointId}/workflow`
      );
      if (!response.ok) throw new Error('Failed to fetch endpoint workflow');
      return response.json();
    },
    enabled: !!repositoryId && !!endpointId,
  });
}

// ============================================================================
// Investigation Hooks (Phase 16)
// ============================================================================

export interface InvestigationRequest {
  question: string;
  analysis_run_id?: string;
  conversation_context?: {
    last_symbols?: Array<{ id: string; name: string; type: string }>;
    last_files?: string[];
    last_endpoints?: Array<{ id: string; method: string; path: string }>;
    last_question?: string;
  };
  max_evidence?: number;
  include_graph?: boolean;
  include_workflow?: boolean;
  include_git_history?: boolean;
}

export function useInvestigate(repositoryId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (request: InvestigationRequest) => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/investigate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        }
      );
      if (!response.ok) {
        throw await requestError(response, 'Investigation is temporarily unavailable.');
      }
      return response.json() as Promise<InvestigationResponse>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repository', repositoryId, 'investigation'] });
    },
  });
}

export function useInvestigationInfo(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'investigation-info'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/investigation-info`
      );
      if (!response.ok) throw new Error('Failed to fetch investigation info');
      return response.json();
    },
    enabled: !!repositoryId,
  });
}

// ============================================================================
// Impact Analysis Hooks (Phase 13)
// ============================================================================

export function useImpactAnalysis(repositoryId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (request: any) => {
      const response = await fetch(
        `${API_BASE_URL}/api/impact-analysis/repositories/${repositoryId}/analyze`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        }
      );
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Impact analysis failed');
      }
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repository', repositoryId, 'impact'] });
    },
  });
}

// ============================================================================
// Background Jobs Hooks (Phase 14)
// ============================================================================

export function useJob(jobId: string) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
      if (!response.ok) throw await requestError(response, 'Unable to load analysis status.');
      return response.json() as Promise<BackgroundJob>;
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'queued' ? 2000 : false;
    },
  });
}

export function useLatestJobForRepository(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'latest-job'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/latest-job`
      );
      if (response.status === 404) return null;
      if (!response.ok) throw await requestError(response, 'Unable to load analysis status.');
      return response.json() as Promise<BackgroundJob>;
    },
    enabled: !!repositoryId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'queued' ? 2000 : false;
    },
  });
}

export function useCancelJob() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (jobId: string) => {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/cancel`, {
        method: 'POST',
      });
      if (!response.ok) throw await requestError(response, 'Unable to cancel analysis.');
      return response.json();
    },
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
    },
  });
}

export function useStartAnalysis() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (url: string) => {
      const response = await fetch(`${API_BASE_URL}/api/repositories/analyze-async`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      if (!response.ok) {
        throw await requestError(response, 'Unable to start analysis.');
      }
      return response.json() as Promise<StartedAnalysis>;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['repository', data.repository_id] });
      queryClient.invalidateQueries({ queryKey: ['repository', data.repository_id, 'latest-analysis'] });
      queryClient.invalidateQueries({ queryKey: ['repository', data.repository_id, 'latest-job'] });
    },
  });
}

// ============================================================================
// Search Hooks
// ============================================================================

export function useGlobalSearch(repositoryId: string, query: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'search', query],
    queryFn: async () => {
      if (!query || query.length < 2) return { results: [] };

      const params = new URLSearchParams({ search: query, limit: '1000' });
      const symbolParams = new URLSearchParams({ name: query, limit: '1000' });
      const [filesResponse, symbolsResponse, endpointsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/files?${params}`),
        fetch(`${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/symbols?${symbolParams}`),
        fetch(`${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/endpoints?page_size=100`),
      ]);

      if (!filesResponse.ok) throw await requestError(filesResponse, 'Unable to search repository files.');
      if (!symbolsResponse.ok) throw await requestError(symbolsResponse, 'Unable to search repository symbols.');
      if (!endpointsResponse.ok) throw await requestError(endpointsResponse, 'Unable to search API endpoints.');

      const [files, symbols, endpointData] = await Promise.all([
        filesResponse.json() as Promise<RepositoryFile[]>,
        symbolsResponse.json() as Promise<Array<{ name: string; file: string; type: string }>>,
        endpointsResponse.json() as Promise<{ items?: Array<{ path: string; handler_name?: string | null; file_path: string }> }>,
      ]);
      const normalizedQuery = query.toLowerCase();
      return {
        files: files.filter((file) => file.path.toLowerCase().includes(normalizedQuery)),
        symbols,
        endpoints: (endpointData.items || []).filter((endpoint) =>
          [endpoint.path, endpoint.handler_name, endpoint.file_path]
            .some((value) => value?.toLowerCase().includes(normalizedQuery))
        ),
      };
    },
    enabled: !!repositoryId && query.length >= 2,
  });
}

// ============================================================================
// Git History Hooks
// ============================================================================

export function useCommits(repositoryId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'commits'],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/git-history/repositories/${repositoryId}/commits`
      );
      if (!response.ok) throw new Error('Failed to fetch commits');
      return response.json();
    },
    enabled: !!repositoryId,
  });
}

export function useCommitDetail(repositoryId: string, commitId: string) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'commit', commitId],
    queryFn: async () => {
      const response = await fetch(
        `${API_BASE_URL}/api/git-history/repositories/${repositoryId}/commits/${commitId}`
      );
      if (!response.ok) throw new Error('Failed to fetch commit detail');
      return response.json();
    },
    enabled: !!repositoryId && !!commitId,
  });
}

// ============================================================================
// Ask Hooks (Phase 12)
// ============================================================================

export function useAsk(repositoryId: string) {
  return useMutation({
    mutationFn: async (request: { question: string; top_k?: number; analysis_run_id?: string }) => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${repositoryId}/ask`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        }
      );
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Question failed');
      }
      return response.json();
    },
  });
}

// ============================================================================
// Change Analysis Hooks (Phase 18)
// ============================================================================

export * from './hooks/use-change-analysis';
