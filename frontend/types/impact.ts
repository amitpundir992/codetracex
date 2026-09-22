/**
 * TypeScript types for Phase 13: AI Impact Analysis + Change Planning
 */

export interface ImpactTarget {
  target_type: 'symbol' | 'file' | 'api_endpoint';
  target_id: string;
  name: string;
  symbol_type?: string;
  qualified_name?: string;
  file_path?: string;
  language?: string;
  http_method?: string;
  endpoint_path?: string;
  framework?: string;
  handler_name?: string;
}

export interface TargetCandidate {
  target: ImpactTarget;
  match_score: number;
  match_reason: string;
}

export interface TargetIdentificationResult {
  status: 'found' | 'ambiguous' | 'not_found';
  target?: ImpactTarget;
  candidates?: TargetCandidate[];
  message?: string;
}

export interface ImpactEvidence {
  source_type: 'dependency_graph' | 'api_analysis' | 'workflow_analysis' | 'git_history' | 'semantic_search' | 'keyword_search' | 'hybrid_search';
  file_path: string;
  start_line?: number;
  end_line?: number;
  symbol_name?: string;
  symbol_type?: string;
  relationship_type: string;
  relationship_direction: 'outgoing' | 'incoming';
  excerpt?: string;
}

export interface ImpactItem {
  impact_category: 'direct_caller' | 'transitive_caller' | 'direct_callee' | 'transitive_callee' | 
    'dependent_file' | 'dependency_file' | 'api_endpoint' | 'workflow' | 'test' | 'historical_cochange';
  entity_type: 'symbol' | 'file' | 'api_endpoint';
  entity_id: string;
  entity_name: string;
  symbol_type?: string;
  file_path?: string;
  http_method?: string;
  endpoint_path?: string;
  depth: number;
  reason: string;
  evidence: ImpactEvidence[];
}

export interface ImpactSummary {
  total_impacts: number;
  direct_impacts: number;
  transitive_impacts: number;
  affected_files_count: number;
  affected_symbols_count: number;
  affected_endpoints_count: number;
  max_depth_reached: number;
  has_api_impact: boolean;
  has_workflow_impact: boolean;
  has_test_impact: boolean;
}

export interface TruncationInfo {
  is_truncated: boolean;
  truncation_reason?: string;
  nodes_analyzed: number;
  edges_analyzed: number;
  max_nodes: number;
  max_edges: number;
}

export interface ImplementationStep {
  step_number: number;
  action: string;
  target_files: string[];
  target_symbols: string[];
  reason: string;
  evidence_references: string[];
  depends_on_steps: number[];
  risk_level: 'low' | 'medium' | 'high' | 'unknown';
  uncertainty_note?: string;
}

export interface ImplementationPlan {
  summary: string;
  steps: ImplementationStep[];
  estimated_files_affected: number;
  overall_risk: 'low' | 'medium' | 'high' | 'unknown';
  assumptions: string[];
  limitations: string[];
}

export interface ImpactCitation {
  source_type: 'graph_analysis' | 'api_analysis' | 'workflow_analysis' | 'git_history' | 'code_search';
  file_path: string;
  start_line?: number;
  end_line?: number;
  symbol_name?: string;
  claim: string;
  excerpt?: string;
}

export interface ImpactAnalysisRequest {
  question: string;
  target_type?: 'symbol' | 'file' | 'api_endpoint';
  target_id?: string;
  depth?: number;
  include_implementation_plan?: boolean;
  analysis_run_id?: string;
}

export interface ImpactAnalysisResponse {
  status: 'success' | 'ambiguous_target' | 'target_not_found' | 'insufficient_evidence';
  question: string;
  target?: ImpactTarget;
  target_identification?: TargetIdentificationResult;
  summary?: ImpactSummary;
  impacts: ImpactItem[];
  affected_files: string[];
  affected_endpoints: Array<{
    method: string;
    path: string;
    handler: string;
    file: string;
  }>;
  affected_workflows: Array<{
    entry_point: string;
    entry_type: string;
    node_count: number;
    edge_count: number;
  }>;
  historical_evidence: any[];
  explanation?: string;
  implementation_plan?: ImplementationPlan;
  citations: ImpactCitation[];
  confidence_note?: string;
  truncation?: TruncationInfo;
  analysis_run_id?: string;
  repository_id: string;
}
