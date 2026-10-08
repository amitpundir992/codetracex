/**
 * Phase 18: Change Intelligence API Hook
 */

import { useMutation } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChangeAnalysisRequest {
  commit_sha?: string;
  base_commit?: string;
  head_commit?: string;
  pr_number?: number;
}

export interface ChangedFile {
  path: string;
  change_type: 'added' | 'modified' | 'deleted';
  additions?: number;
  deletions?: number;
}

export interface ChangedSymbol {
  name: string;
  qualified_name: string;
  symbol_type: string;
  change_type: string;
  file_path: string;
  line_number?: number;
  is_public: boolean;
}

export interface AffectedEndpoint {
  method: string;
  route: string;
  handler?: string;
  file_path: string;
  directly_affected: boolean;
}

export interface AffectedWorkflow {
  workflow_id?: string;
  workflow_name: string;
  affected_tasks?: string[];
}

export interface RelevantTest {
  test_file: string;
  test_name?: string;
  relevance_reason: string;
}

export interface RiskSignal {
  signal_type: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
}

export interface ChangeAnalysisResponse {
  summary: {
    total_files_changed: number;
    total_symbols_changed: number;
    commit?: string;
    commit_range?: {
      base: string;
      head: string;
    };
  };
  files_changed: ChangedFile[];
  changed_symbols: ChangedSymbol[];
  dependency_impact: {
    affected_symbols: number;
    graph_traversal: {
      total_callers: number;
      total_callees: number;
      max_depth_reached: number;
      truncated: boolean;
    };
  };
  api_impact: {
    affected_endpoints: AffectedEndpoint[];
    total_endpoints_affected: number;
  };
  workflow_impact: {
    affected_workflows: AffectedWorkflow[];
    total_workflows_affected: number;
  };
  test_intelligence: {
    relevant_tests: RelevantTest[];
    total_tests: number;
    confidence: string;
  };
  risk_assessment: {
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    risk_score: number;
    signals: RiskSignal[];
    summary: string;
  };
  evidence: {
    key_evidence: string[];
    limitations: string[];
  };
  llm_analysis?: {
    summary: string;
    potential_issues: string[];
    recommendations: string[];
  };
}

export function useChangeAnalysis(repositoryId: string) {
  return useMutation({
    mutationFn: async (request: ChangeAnalysisRequest) => {
      const response = await fetch(
        `${API_BASE_URL}/api/repositories/${encodeURIComponent(repositoryId)}/change-analysis`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
        }
      );
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Change analysis failed' }));
        throw new Error(error.detail || 'Change analysis failed');
      }
      return response.json() as Promise<ChangeAnalysisResponse>;
    },
  });
}
