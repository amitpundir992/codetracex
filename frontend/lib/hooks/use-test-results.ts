/**
 * React Query hooks for Phase 20: Test Results & Failure Intelligence
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../api';
import type {
  TestResultImportRequest,
  TestResultImportResponse,
  TestRunListResponse,
  TestRunDetailResponse,
  TestFailuresResponse,
  FailureExplainRequest,
  FailureExplainResponse
} from '@/types/test-results';

/**
 * Hook to list test runs for a repository.
 * 
 * @param repositoryId - Repository UUID
 * @param limit - Results per page (default: 50)
 * @param offset - Pagination offset (default: 0)
 * @param commitSha - Optional commit SHA filter
 */
export function useTestRuns(
  repositoryId: string,
  limit: number = 50,
  offset: number = 0,
  commitSha?: string
) {
  return useQuery({
    queryKey: ['testRuns', repositoryId, limit, offset, commitSha],
    queryFn: () => api.listTestRuns(repositoryId, limit, offset, commitSha),
    enabled: !!repositoryId,
  });
}

/**
 * Hook to get detailed test run information.
 * 
 * @param repositoryId - Repository UUID
 * @param runId - Test run UUID
 */
export function useTestRunDetail(repositoryId: string, runId: string) {
  return useQuery({
    queryKey: ['testRunDetail', repositoryId, runId],
    queryFn: () => api.getTestRunDetail(repositoryId, runId),
    enabled: !!repositoryId && !!runId,
  });
}

/**
 * Hook to get test failures with analysis.
 * 
 * @param repositoryId - Repository UUID
 * @param runId - Test run UUID
 */
export function useTestFailures(repositoryId: string, runId: string) {
  return useQuery({
    queryKey: ['testFailures', repositoryId, runId],
    queryFn: () => api.getTestFailures(repositoryId, runId),
    enabled: !!repositoryId && !!runId,
  });
}

/**
 * Hook to import test results.
 * 
 * Returns mutation for importing test results.
 * Invalidates test runs query on success.
 * 
 * @param repositoryId - Repository UUID
 */
export function useImportTestResults(repositoryId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: TestResultImportRequest) =>
      api.importTestResults(repositoryId, request),
    onSuccess: () => {
      // Invalidate test runs list to refetch
      queryClient.invalidateQueries({
        queryKey: ['testRuns', repositoryId],
      });
    },
  });
}

/**
 * Hook to generate LLM explanation for a test failure.
 * 
 * @param repositoryId - Repository UUID
 */
export function useExplainTestFailure(repositoryId: string) {
  return useMutation({
    mutationFn: (request: FailureExplainRequest) =>
      api.explainTestFailure(repositoryId, request),
  });
}
