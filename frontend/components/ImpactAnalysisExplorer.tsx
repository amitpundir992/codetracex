/**
 * Phase 13: AI Impact Analysis + Change Planning
 * 
 * ImpactAnalysisExplorer component provides an interface for analyzing
 * the impact of potential code changes and generating implementation plans.
 * 
 * Features:
 * - Question input for change impact queries
 * - Target identification (automatic or manual)
 * - Impact summary visualization
 * - Affected files, endpoints, and workflows
 * - LLM-generated explanation
 * - Implementation plan with steps
 * - Risk assessment
 * - Truncation warnings
 */
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { analyzeImpact } from '@/lib/api';
import { ImpactAnalysisResponse, ImpactTarget, ImpactSummary, ImplementationPlan } from '@/types/impact';
import { 
  Loader2, 
  AlertCircle, 
  Target, 
  FileText, 
  AlertTriangle, 
  CheckCircle, 
  Info,
  GitBranch,
  Globe,
  Workflow as WorkflowIcon
} from 'lucide-react';

interface ImpactAnalysisExplorerProps {
  repositoryId: string;
  analysisRunId?: string;
}

export default function ImpactAnalysisExplorer({ 
  repositoryId, 
  analysisRunId 
}: ImpactAnalysisExplorerProps) {
  const [question, setQuestion] = useState('');
  const [depth, setDepth] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImpactAnalysisResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate input
    if (!question.trim()) {
      setError('Please enter a question about a potential change');
      return;
    }
    
    // Clear previous state
    setError(null);
    setResult(null);
    setLoading(true);
    
    try {
      const analysisResult = await analyzeImpact(repositoryId, {
        question: question.trim(),
        depth,
        include_implementation_plan: true,
        analysis_run_id: analysisRunId,
      });
      setResult(analysisResult);
    } catch (err: any) {
      // Handle different error types
      if (err.status === 503) {
        setError('LLM service is not available. Please configure LLM_API_KEY in the backend.');
      } else if (err.status === 504) {
        setError('The request timed out. Please try again.');
      } else if (err.status === 429) {
        setError('Rate limit exceeded. Please wait a moment and try again.');
      } else {
        setError(err.detail || err.message || 'Failed to analyze impact');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExampleQuestion = (exampleQuestion: string) => {
    setQuestion(exampleQuestion);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-primary" />
            <CardTitle>Impact Analysis & Change Planning</CardTitle>
          </div>
          <CardDescription>
            Analyze what would be affected by a potential change and get an implementation plan.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Question Input */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="question" className="text-sm font-medium">
                What change do you want to analyze?
              </label>
              <Input
                id="question"
                type="text"
                placeholder="What would be affected if I change OrderService.create_order?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label htmlFor="depth" className="text-sm font-medium">
                  Analysis Depth:
                </label>
                <select
                  id="depth"
                  value={depth}
                  onChange={(e) => setDepth(Number(e.target.value))}
                  disabled={loading}
                  className="border rounded px-2 py-1 text-sm"
                >
                  <option value="1">1 (Direct only)</option>
                  <option value="2">2</option>
                  <option value="3">3 (Default)</option>
                  <option value="5">5</option>
                  <option value="10">10 (Maximum)</option>
                </select>
              </div>

              <Button type="submit" disabled={loading || !question.trim()}>
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  'Analyze Impact'
                )}
              </Button>
            </div>

            {/* Example Questions */}
            {!result && !loading && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Example questions:</p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleExampleQuestion('What files would I need to modify to add Google OAuth?')}
                    disabled={loading}
                  >
                    Add OAuth
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleExampleQuestion('If I change the response shape of POST /api/orders, what could be affected?')}
                    disabled={loading}
                  >
                    API change impact
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleExampleQuestion('How would I add email notifications to order creation?')}
                    disabled={loading}
                  >
                    Add feature
                  </Button>
                </div>
              </div>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-destructive">Error</p>
                <p className="text-sm text-muted-foreground mt-1">{error}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Result Display */}
      {result && (
        <div className="space-y-6">
          {/* Status Handling */}
          {result.status === 'target_not_found' && (
            <Card className="border-yellow-500">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium">Target Not Found</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {result.confidence_note || 'Could not identify a specific code entity from your question.'}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {result.status === 'ambiguous_target' && result.target_identification && (
            <Card className="border-yellow-500">
              <CardContent className="pt-6">
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium">Multiple Matches Found</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        {result.confidence_note || 'Please specify which target you want to analyze.'}
                      </p>
                    </div>
                  </div>
                  {result.target_identification.candidates && (
                    <div className="ml-8 space-y-2">
                      <p className="text-sm font-medium">Candidates:</p>
                      <ul className="space-y-2">
                        {result.target_identification.candidates.map((candidate, idx) => (
                          <li key={idx} className="text-sm">
                            <span className="font-medium">{candidate.target.name}</span>
                            {candidate.target.file_path && (
                              <span className="text-muted-foreground"> in {candidate.target.file_path}</span>
                            )}
                            <span className="text-muted-foreground"> ({candidate.match_score.toFixed(2)} confidence)</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Success - Show Full Analysis */}
          {result.status === 'success' && result.target && result.summary && (
            <>
              {/* Target */}
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    <Target className="w-5 h-5" />
                    <CardTitle className="text-lg">Target</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <p className="font-medium text-lg">{result.target.name}</p>
                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      <span>Type: {result.target.target_type}</span>
                      {result.target.file_path && <span>File: {result.target.file_path}</span>}
                      {result.target.language && <span>Language: {result.target.language}</span>}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Truncation Warning */}
              {result.truncation?.is_truncated && (
                <Card className="border-yellow-500">
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="font-medium">Analysis Truncated</p>
                        <p className="text-sm text-muted-foreground mt-1">
                          Analysis was truncated due to: {result.truncation.truncation_reason}. 
                          Actual impact may be larger than shown.
                        </p>
                        <p className="text-sm text-muted-foreground">
                          Analyzed: {result.truncation.nodes_analyzed}/{result.truncation.max_nodes} nodes, 
                          {result.truncation.edges_analyzed}/{result.truncation.max_edges} edges
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Impact Summary */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Impact Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-2xl font-bold">{result.summary.total_impacts}</p>
                      <p className="text-sm text-muted-foreground">Total Impacts</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{result.summary.affected_files_count}</p>
                      <p className="text-sm text-muted-foreground">Affected Files</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{result.summary.affected_endpoints_count}</p>
                      <p className="text-sm text-muted-foreground">Affected APIs</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{result.summary.max_depth_reached}</p>
                      <p className="text-sm text-muted-foreground">Max Depth</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {result.summary.has_api_impact && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-800 text-xs rounded">
                        <Globe className="w-3 h-3" />
                        API Impact
                      </span>
                    )}
                    {result.summary.has_workflow_impact && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-800 text-xs rounded">
                        <WorkflowIcon className="w-3 h-3" />
                        Workflow Impact
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* LLM Explanation */}
              {result.explanation && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Info className="w-5 h-5" />
                      <CardTitle className="text-lg">Impact Explanation</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="prose prose-sm max-w-none">
                      <p className="whitespace-pre-wrap">{result.explanation}</p>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Implementation Plan */}
              {result.implementation_plan && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <GitBranch className="w-5 h-5" />
                      <CardTitle className="text-lg">Implementation Plan</CardTitle>
                    </div>
                    <CardDescription>
                      {result.implementation_plan.summary}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Overall Risk */}
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">Overall Risk:</span>
                      <span className={`px-2 py-1 text-xs rounded ${
                        result.implementation_plan.overall_risk === 'high' ? 'bg-red-100 text-red-800' :
                        result.implementation_plan.overall_risk === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-green-100 text-green-800'
                      }`}>
                        {result.implementation_plan.overall_risk.toUpperCase()}
                      </span>
                      <span className="text-sm text-muted-foreground ml-2">
                        ~{result.implementation_plan.estimated_files_affected} files affected
                      </span>
                    </div>

                    {/* Steps */}
                    <div className="space-y-4">
                      <h3 className="font-medium">Steps:</h3>
                      {result.implementation_plan.steps.map((step, idx) => (
                        <div key={idx} className="border-l-2 border-primary pl-4 py-2">
                          <div className="flex items-start gap-2">
                            <span className="font-bold text-primary">{step.step_number}.</span>
                            <div className="flex-1 space-y-2">
                              <p className="font-medium">{step.action}</p>
                              <p className="text-sm text-muted-foreground">{step.reason}</p>
                              
                              {step.target_files.length > 0 && (
                                <div className="text-xs">
                                  <span className="font-medium">Files: </span>
                                  {step.target_files.join(', ')}
                                </div>
                              )}
                              
                              <div className="flex items-center gap-2">
                                <span className={`px-2 py-0.5 text-xs rounded ${
                                  step.risk_level === 'high' ? 'bg-red-100 text-red-800' :
                                  step.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                                  step.risk_level === 'low' ? 'bg-green-100 text-green-800' :
                                  'bg-gray-100 text-gray-800'
                                }`}>
                                  {step.risk_level} risk
                                </span>
                                
                                {step.depends_on_steps.length > 0 && (
                                  <span className="text-xs text-muted-foreground">
                                    Depends on step(s): {step.depends_on_steps.join(', ')}
                                  </span>
                                )}
                              </div>
                              
                              {step.uncertainty_note && (
                                <div className="flex items-start gap-1 text-xs text-muted-foreground">
                                  <AlertTriangle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                                  <span>{step.uncertainty_note}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Limitations */}
                    {result.implementation_plan.limitations && result.implementation_plan.limitations.length > 0 && (
                      <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
                        <p className="font-medium text-sm mb-2">⚠️ Limitations:</p>
                        <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                          {result.implementation_plan.limitations.map((limitation, idx) => (
                            <li key={idx}>{limitation}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Affected Files */}
              {result.affected_files && result.affected_files.length > 0 && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <FileText className="w-5 h-5" />
                      <CardTitle className="text-lg">Affected Files ({result.affected_files.length})</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1 text-sm">
                      {result.affected_files.slice(0, 20).map((file, idx) => (
                        <li key={idx} className="font-mono text-xs">{file}</li>
                      ))}
                      {result.affected_files.length > 20 && (
                        <li className="text-muted-foreground">
                          ... and {result.affected_files.length - 20} more files
                        </li>
                      )}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* Affected Endpoints */}
              {result.affected_endpoints && result.affected_endpoints.length > 0 && (
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Globe className="w-5 h-5" />
                      <CardTitle className="text-lg">Affected API Endpoints ({result.affected_endpoints.length})</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2 text-sm">
                      {result.affected_endpoints.map((endpoint, idx) => (
                        <li key={idx} className="border-l-2 border-primary pl-3 py-1">
                          <span className="font-medium font-mono">{endpoint.method} {endpoint.path}</span>
                          <div className="text-xs text-muted-foreground">
                            Handler: {endpoint.handler} in {endpoint.file}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
