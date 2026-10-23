/**
 * Phase 23: Traceability Explorer Hooks
 * 
 * React Query hooks for Phase 22 test-to-code traceability APIs
 */

import { useQuery } from '@tanstack/react-query';
import type {
  SourceTraceabilityResponse,
  SymbolTraceabilityResponse,
  TestTraceabilityResponse,
  SourceTraceabilityRequest,
  SymbolTraceabilityRequest,
  TestTraceabilityRequest,
} from '@/types/traceability';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Get tests related to a source file
 */
export function useSourceToTests(
  repositoryId: string,
  request: SourceTraceabilityRequest
) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'traceability', 'source-to-tests', request],
    queryFn: async () => {
      const params = new URLSearchParams({
        source_file: request.source_file,
      });
      if (request.analysis_run_id) {
        params.append('analysis_run_id', request.analysis_run_id);
      }

      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/traceability/source-to-tests?${params.toString()}`,
        {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get source traceability' }));
        throw new Error(error.detail || 'Failed to get source traceability');
      }

      return response.json() as Promise<SourceTraceabilityResponse>;
    },
    enabled: !!repositoryId && !!request.source_file,
  });
}

/**
 * Get tests related to a symbol
 */
export function useSymbolToTests(
  repositoryId: string,
  request: SymbolTraceabilityRequest
) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'traceability', 'symbol-to-tests', request],
    queryFn: async () => {
      const params = new URLSearchParams({
        symbol_name: request.symbol_name,
      });
      if (request.file_path) {
        params.append('file_path', request.file_path);
      }
      if (request.analysis_run_id) {
        params.append('analysis_run_id', request.analysis_run_id);
      }

      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/traceability/symbol-to-tests?${params.toString()}`,
        {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get symbol traceability' }));
        throw new Error(error.detail || 'Failed to get symbol traceability');
      }

      return response.json() as Promise<SymbolTraceabilityResponse>;
    },
    enabled: !!repositoryId && !!request.symbol_name,
  });
}

/**
 * Get source files related to a test
 */
export function useTestToSources(
  repositoryId: string,
  request: TestTraceabilityRequest
) {
  return useQuery({
    queryKey: ['repository', repositoryId, 'traceability', 'test-to-sources', request],
    queryFn: async () => {
      const params = new URLSearchParams({
        test_file: request.test_file,
      });
      if (request.analysis_run_id) {
        params.append('analysis_run_id', request.analysis_run_id);
      }

      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/traceability/test-to-sources?${params.toString()}`,
        {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        }
      );

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to get test traceability' }));
        throw new Error(error.detail || 'Failed to get test traceability');
      }

      return response.json() as Promise<TestTraceabilityResponse>;
    },
    enabled: !!repositoryId && !!request.test_file,
  });
}
