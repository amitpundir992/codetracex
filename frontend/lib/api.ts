/**
 * API client for communicating with the CodeTraceX backend.
 */

import { 
  RepositoryRequest, 
  RepositoryResponse, 
  RepositoryAnalysisResponse,
  SymbolCallersResponse,
  SymbolCalleesResponse,
  SymbolDependenciesResponse,
  SymbolDependentsResponse,
  FileDependenciesResponse,
  FileDependentsResponse,
  ImpactAnalysisResponse,
  PaginatedCommitResponse,
  CommitDetail,
  FileHistoryResponse,
  CoChangeResponse,
  PaginatedApiEndpointsResponse,
  ApiEndpointDetail,
  ApiEndpointDependencies,
  WorkflowResponse
} from '@/types/repository';
import { AskRequest, AskResponse } from '@/types/llm';
import { 
  ImpactAnalysisRequest, 
  ImpactAnalysisResponse as ImpactResponse 
} from '@/types/impact';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Custom error class for API errors.
 */
export class APIError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public detail?: string
  ) {
    super(message);
    this.name = 'APIError';
  }
}

/**
 * Response type for async analysis job creation.
 */
export interface AsyncAnalysisResponse {
  job_id: string;
  analysis_run_id: string;
  repository_id: string;
  status: string;
}

/**
 * Ingest a GitHub repository and retrieve its metadata.
 * 
 * @param url - GitHub repository URL
 * @returns Repository metadata
 * @throws APIError if the request fails
 */
export async function ingestRepository(url: string): Promise<RepositoryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/repositories`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url } as RepositoryRequest),
  });

  if (!response.ok) {
    let detail = 'An error occurred while processing your request';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: RepositoryResponse = await response.json();
  return data;
}

/**
 * Analyze a GitHub repository (Phase 2).
 * 
 * Downloads the repository, scans files, and returns file metadata and statistics.
 * 
 * @param url - GitHub repository URL
 * @returns Repository analysis results
 * @throws APIError if the request fails
 */
export async function analyzeRepository(url: string): Promise<RepositoryAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/repositories/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url } as RepositoryRequest),
  });

  if (!response.ok) {
    let detail = 'An error occurred while analyzing the repository';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: RepositoryAnalysisResponse = await response.json();
  return data;
}

/**
 * Start asynchronous repository analysis (Phase 14).
 * 
 * Enqueues a background job to analyze a GitHub repository.
 * Returns immediately with a job ID that can be used to track progress.
 * 
 * @param url - GitHub repository URL
 * @returns Job information
 * @throws APIError if the request fails
 */
export async function analyzeRepositoryAsync(url: string): Promise<AsyncAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/api/repositories/analyze-async`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url } as RepositoryRequest),
  });

  if (!response.ok) {
    let detail = 'An error occurred while starting repository analysis';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: AsyncAnalysisResponse = await response.json();
  return data;
}

/**
 * Get callers of a symbol (Phase 5).
 * 
 * @param repositoryId - Repository UUID
 * @param symbolId - Symbol UUID
 * @param depth - Traversal depth (1-10)
 * @returns Symbol callers
 * @throws APIError if the request fails
 */
export async function getSymbolCallers(
  repositoryId: string,
  symbolId: string,
  depth: number = 1
): Promise<SymbolCallersResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/symbols/${symbolId}/callers?depth=${depth}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch symbol callers';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: SymbolCallersResponse = await response.json();
  return data;
}

/**
 * Get callees of a symbol (Phase 5).
 * 
 * @param repositoryId - Repository UUID
 * @param symbolId - Symbol UUID
 * @param depth - Traversal depth (1-10)
 * @returns Symbol callees
 * @throws APIError if the request fails
 */
export async function getSymbolCallees(
  repositoryId: string,
  symbolId: string,
  depth: number = 1
): Promise<SymbolCalleesResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/symbols/${symbolId}/callees?depth=${depth}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch symbol callees';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: SymbolCalleesResponse = await response.json();
  return data;
}

/**
 * Get dependencies of a symbol (Phase 5).
 * 
 * @param repositoryId - Repository UUID
 * @param symbolId - Symbol UUID
 * @param depth - Traversal depth (1-10)
 * @returns Symbol dependencies
 * @throws APIError if the request fails
 */
export async function getSymbolDependencies(
  repositoryId: string,
  symbolId: string,
  depth: number = 1
): Promise<SymbolDependenciesResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/symbols/${symbolId}/dependencies?depth=${depth}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch symbol dependencies';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: SymbolDependenciesResponse = await response.json();
  return data;
}

/**
 * Get dependents of a symbol (Phase 5).
 * 
 * @param repositoryId - Repository UUID
 * @param symbolId - Symbol UUID
 * @param depth - Traversal depth (1-10)
 * @returns Symbol dependents
 * @throws APIError if the request fails
 */
export async function getSymbolDependents(
  repositoryId: string,
  symbolId: string,
  depth: number = 1
): Promise<SymbolDependentsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/symbols/${symbolId}/dependents?depth=${depth}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch symbol dependents';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: SymbolDependentsResponse = await response.json();
  return data;
}

/**
 * Get impact analysis for a symbol (Phase 5).
 * 
 * @param repositoryId - Repository UUID
 * @param symbolId - Symbol UUID
 * @param maxDepth - Maximum traversal depth (1-10)
 * @returns Impact analysis
 * @throws APIError if the request fails
 */
export async function getSymbolImpact(
  repositoryId: string,
  symbolId: string,
  maxDepth: number = 5
): Promise<ImpactAnalysisResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/symbols/${symbolId}/impact?max_depth=${maxDepth}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch impact analysis';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: ImpactAnalysisResponse = await response.json();
  return data;
}

/**
 * Get file dependencies (Phase 5).
 * 
 * @param repositoryId - Repository UUID
 * @param fileId - File UUID
 * @returns File dependencies
 * @throws APIError if the request fails
 */
export async function getFileDependencies(
  repositoryId: string,
  fileId: string
): Promise<FileDependenciesResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/files/${fileId}/dependencies`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch file dependencies';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: FileDependenciesResponse = await response.json();
  return data;
}

/**
 * Get file dependents (Phase 5).
 * 
 * @param repositoryId - Repository UUID
 * @param fileId - File UUID
 * @returns File dependents
 * @throws APIError if the request fails
 */
export async function getFileDependents(
  repositoryId: string,
  fileId: string
): Promise<FileDependentsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/files/${fileId}/dependents`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch file dependents';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: FileDependentsResponse = await response.json();
  return data;
}

/**
 * Get commits for a repository (Phase 6).
 * 
 * @param repositoryId - Repository UUID
 * @param page - Page number (1-indexed)
 * @param pageSize - Results per page (max 100)
 * @returns Paginated commit list
 * @throws APIError if the request fails
 */
export async function getRepositoryCommits(
  repositoryId: string,
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedCommitResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/commits?page=${page}&page_size=${pageSize}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch commits';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: PaginatedCommitResponse = await response.json();
  return data;
}

/**
 * Get commit details (Phase 6).
 * 
 * @param repositoryId - Repository UUID
 * @param commitId - Commit UUID
 * @returns Commit details with file changes
 * @throws APIError if the request fails
 */
export async function getCommitDetails(
  repositoryId: string,
  commitId: string
): Promise<CommitDetail> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/commits/${commitId}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch commit details';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: CommitDetail = await response.json();
  return data;
}

/**
 * Get file history (Phase 6).
 * 
 * @param repositoryId - Repository UUID
 * @param fileId - File UUID
 * @param limit - Maximum number of commits (max 200)
 * @returns File commit history
 * @throws APIError if the request fails
 */
export async function getFileHistory(
  repositoryId: string,
  fileId: string,
  limit: number = 50
): Promise<FileHistoryResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/files/${fileId}/history?limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch file history';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: FileHistoryResponse = await response.json();
  return data;
}

/**
 * Get file co-changes (Phase 6).
 * 
 * @param repositoryId - Repository UUID
 * @param fileId - File UUID
 * @param minSharedCommits - Minimum shared commits threshold
 * @param limit - Maximum results (max 100)
 * @returns Files frequently changed together
 * @throws APIError if the request fails
 */
export async function getFileCoChanges(
  repositoryId: string,
  fileId: string,
  minSharedCommits: number = 2,
  limit: number = 20
): Promise<CoChangeResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/files/${fileId}/co-changes?min_shared_commits=${minSharedCommits}&limit=${limit}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch co-change data';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: CoChangeResponse = await response.json();
  return data;
}

/**
 * Get API endpoints for a repository (Phase 7).
 * 
 * @param repositoryId - Repository UUID
 * @param page - Page number
 * @param pageSize - Items per page
 * @param method - Filter by HTTP method (optional)
 * @param framework - Filter by framework (optional)
 * @returns Paginated list of API endpoints
 * @throws APIError if the request fails
 */
export async function getRepositoryEndpoints(
  repositoryId: string,
  page: number = 1,
  pageSize: number = 20,
  method?: string,
  framework?: string
): Promise<PaginatedApiEndpointsResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });
  
  if (method) {
    params.append('method', method);
  }
  
  if (framework) {
    params.append('framework', framework);
  }
  
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/endpoints?${params.toString()}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch API endpoints';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: PaginatedApiEndpointsResponse = await response.json();
  return data;
}

/**
 * Get detailed information about a specific API endpoint (Phase 7).
 * 
 * @param repositoryId - Repository UUID
 * @param endpointId - Endpoint UUID
 * @returns Detailed endpoint information
 * @throws APIError if the request fails
 */
export async function getEndpointDetails(
  repositoryId: string,
  endpointId: string
): Promise<ApiEndpointDetail> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/endpoints/${endpointId}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch endpoint details';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: ApiEndpointDetail = await response.json();
  return data;
}

/**
 * Get dependencies for a specific API endpoint (Phase 7).
 * 
 * @param repositoryId - Repository UUID
 * @param endpointId - Endpoint UUID
 * @param depth - Traversal depth
 * @returns Endpoint dependencies
 * @throws APIError if the request fails
 */
export async function getEndpointDependencies(
  repositoryId: string,
  endpointId: string,
  depth: number = 3
): Promise<ApiEndpointDependencies> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/endpoints/${endpointId}/dependencies?depth=${depth}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch endpoint dependencies';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: ApiEndpointDependencies = await response.json();
  return data;
}

/**
 * Get application workflow for an API endpoint (Phase 8).
 * 
 * Constructs the execution flow starting from the endpoint handler
 * and traversing downstream function calls.
 * 
 * @param repositoryId - Repository UUID
 * @param endpointId - Endpoint UUID
 * @param depth - Traversal depth (1-10, default: 5)
 * @param includeCallers - Include upstream callers (default: false)
 * @returns Workflow graph with nodes and edges
 * @throws APIError if the request fails
 */
export async function getEndpointWorkflow(
  repositoryId: string,
  endpointId: string,
  depth: number = 5,
  includeCallers: boolean = false
): Promise<WorkflowResponse> {
  const params = new URLSearchParams({
    depth: depth.toString(),
    include_callers: includeCallers.toString(),
  });
  
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/endpoints/${endpointId}/workflow?${params.toString()}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch endpoint workflow';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: WorkflowResponse = await response.json();
  return data;
}

/**
 * Get application workflow for a symbol (Phase 8).
 * 
 * Constructs the execution flow starting from a symbol:
 * - downstream: symbol → functions it calls
 * - upstream: symbol → functions that call it
 * - both: bidirectional traversal
 * 
 * @param repositoryId - Repository UUID
 * @param symbolId - Symbol UUID
 * @param depth - Traversal depth (1-10, default: 5)
 * @param direction - Traversal direction (downstream/upstream/both)
 * @returns Workflow graph with nodes and edges
 * @throws APIError if the request fails
 */
export async function getSymbolWorkflow(
  repositoryId: string,
  symbolId: string,
  depth: number = 5,
  direction: 'downstream' | 'upstream' | 'both' = 'downstream'
): Promise<WorkflowResponse> {
  const params = new URLSearchParams({
    depth: depth.toString(),
    direction: direction,
  });
  
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/symbols/${symbolId}/workflow?${params.toString()}`,
    {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  if (!response.ok) {
    let detail = 'Failed to fetch symbol workflow';
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    throw new APIError(
      `API request failed with status ${response.status}`,
      response.status,
      detail
    );
  }

  const data: WorkflowResponse = await response.json();
  return data;
}



/**
 * Ask a question about a repository (Phase 12: LLM Reasoning).
 * 
 * Uses hybrid search to retrieve relevant code context and generates
 * a grounded answer using LLM with citations.
 * 
 * @param repositoryId - Repository UUID
 * @param request - Ask request with question and optional parameters
 * @returns Grounded answer with citations
 * @throws APIError if the request fails
 */
export async function askRepositoryQuestion(
  repositoryId: string,
  request: AskRequest
): Promise<AskResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/ask`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    let detail = 'Failed to generate answer';
    let status = response.status;
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    const error: any = new APIError(
      `API request failed with status ${status}`,
      status,
      detail
    );
    error.status = status;
    throw error;
  }

  const data: AskResponse = await response.json();
  return data;
}

/**
 * Analyze the impact of a potential change (Phase 13).
 * 
 * Performs deterministic impact analysis and generates an implementation plan.
 * 
 * @param repositoryId - Repository UUID
 * @param request - Impact analysis request
 * @returns Impact analysis with explanation and implementation plan
 * @throws APIError if the request fails
 */
export async function analyzeImpact(
  repositoryId: string,
  request: ImpactAnalysisRequest
): Promise<ImpactResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/repositories/${repositoryId}/impact-analysis`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    let detail = 'Failed to analyze impact';
    let status = response.status;
    
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch (e) {
      // If parsing JSON fails, use generic message
    }

    const error: any = new APIError(
      `API request failed with status ${status}`,
      status,
      detail
    );
    error.status = status;
    throw error;
  }

  const data: ImpactResponse = await response.json();
  return data;
}
