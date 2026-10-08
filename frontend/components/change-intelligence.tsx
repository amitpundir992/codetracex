/**
 * Change Intelligence Component - Phase 18
 * 
 * Analyzes code changes (commits, PRs) and provides:
 * - Files changed
 * - Affected symbols
 * - Dependency impact
 * - API impact
 * - Workflow impact
 * - Test intelligence
 * - Risk assessment
 */

'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, AlertTriangle, CheckCircle2, XCircle, FileCode, GitCommit, AlertCircle } from 'lucide-react';
import {
  useChangeAnalysis,
  type ChangeAnalysisResponse,
  type ChangedFile,
  type ChangedSymbol,
  type AffectedEndpoint,
  type RiskSignal,
  ApiRequestError,
  type RepositoryFile,
} from '@/lib/hooks';

interface ChangeIntelligenceProps {
  repositoryId: string;
  files: RepositoryFile[];
  onFileSelect: (file: RepositoryFile, line?: number) => void;
}

export function ChangeIntelligence({ repositoryId, files, onFileSelect }: ChangeIntelligenceProps) {
  const [commitSha, setCommitSha] = useState('');
  const [baseCommit, setBaseCommit] = useState('');
  const [headCommit, setHeadCommit] = useState('');
  const [inputMode, setInputMode] = useState<'commit' | 'range'>('commit');

  const changeAnalysis = useChangeAnalysis(repositoryId);

  const handleAnalyze = () => {
    if (inputMode === 'commit' && commitSha.trim()) {
      changeAnalysis.mutate({ commit_sha: commitSha.trim() });
    } else if (inputMode === 'range' && baseCommit.trim() && headCommit.trim()) {
      changeAnalysis.mutate({
        base_commit: baseCommit.trim(),
        head_commit: headCommit.trim(),
      });
    }
  };

  const selectFile = (path: string, line?: number) => {
    const file = files.find((f) => f.path === path);
    if (file && !file.is_sensitive) {
      onFileSelect(file, line);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-300';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low': return 'bg-green-100 text-green-800 border-green-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getRiskIcon = (level: string) => {
    switch (level) {
      case 'critical':
      case 'high':
        return <AlertTriangle className="h-5 w-5" />;
      case 'medium':
        return <AlertCircle className="h-5 w-5" />;
      case 'low':
        return <CheckCircle2 className="h-5 w-5" />;
      default:
        return null;
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Input Section */}
      <div className="border-b bg-white p-4 space-y-3">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={inputMode === 'commit' ? 'default' : 'outline'}
            onClick={() => setInputMode('commit')}
          >
            Single Commit
          </Button>
          <Button
            size="sm"
            variant={inputMode === 'range' ? 'default' : 'outline'}
            onClick={() => setInputMode('range')}
          >
            Commit Range
          </Button>
        </div>

        {inputMode === 'commit' ? (
          <div className="space-y-2">
            <Input
              placeholder="Enter commit SHA..."
              value={commitSha}
              onChange={(e) => setCommitSha(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            />
          </div>
        ) : (
          <div className="space-y-2">
            <Input
              placeholder="Base commit SHA..."
              value={baseCommit}
              onChange={(e) => setBaseCommit(e.target.value)}
            />
            <Input
              placeholder="Head commit SHA..."
              value={headCommit}
              onChange={(e) => setHeadCommit(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            />
          </div>
        )}

        <Button
          onClick={handleAnalyze}
          disabled={changeAnalysis.isPending ||
            (inputMode === 'commit' && !commitSha.trim()) ||
            (inputMode === 'range' && (!baseCommit.trim() || !headCommit.trim()))}
          className="w-full"
        >
          {changeAnalysis.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Analyzing Changes...
            </>
          ) : (
            <>
              <GitCommit className="mr-2 h-4 w-4" />
              Analyze Change Impact
            </>
          )}
        </Button>
      </div>

      {/* Results Section */}
      <div className="flex-1 overflow-y-auto p-4">
        {changeAnalysis.isError && (
          <Card className="border-red-200 bg-red-50 p-4">
            <p className="text-sm text-red-800">
              {changeAnalysis.error instanceof ApiRequestError
                ? changeAnalysis.error.message
                : 'Unable to analyze changes. Please check the input and try again.'}
            </p>
          </Card>
        )}

        {changeAnalysis.isPending && (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-blue-600" />
              <p className="text-sm text-gray-600">Analyzing change impact...</p>
            </div>
          </div>
        )}

        {changeAnalysis.data && (
          <ChangeAnalysisResults
            data={changeAnalysis.data}
            onFileSelect={selectFile}
            getRiskColor={getRiskColor}
            getRiskIcon={getRiskIcon}
          />
        )}

        {!changeAnalysis.data && !changeAnalysis.isPending && !changeAnalysis.isError && (
          <div className="flex flex-col items-center justify-center py-12 text-gray-500">
            <GitCommit className="mb-4 h-16 w-16 text-gray-300" />
            <p className="text-sm">Enter a commit SHA or range to analyze change impact</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ChangeAnalysisResults({
  data,
  onFileSelect,
  getRiskColor,
  getRiskIcon,
}: {
  data: ChangeAnalysisResponse;
  onFileSelect: (path: string, line?: number) => void;
  getRiskColor: (level: string) => string;
  getRiskIcon: (level: string) => React.ReactNode;
}) {
  return (
    <div className="space-y-4">
      {/* Risk Assessment - Prominent */}
      <Card className={`border-2 p-4 ${getRiskColor(data.risk_assessment.risk_level)}`}>
        <div className="flex items-center gap-3 mb-2">
          {getRiskIcon(data.risk_assessment.risk_level)}
          <div>
            <h3 className="font-semibold">
              Risk Level: {data.risk_assessment.risk_level.toUpperCase()}
            </h3>
            <p className="text-sm">Score: {data.risk_assessment.risk_score}/100</p>
          </div>
        </div>
        <p className="text-sm mt-2">{data.risk_assessment.summary}</p>
        
        {data.risk_assessment.signals.length > 0 && (
          <div className="mt-3 space-y-1">
            {data.risk_assessment.signals.map((signal, idx) => (
              <div key={idx} className="text-xs flex items-start gap-2">
                <span className="font-medium">•</span>
                <span>{signal.description}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Summary */}
      <Card className="p-4">
        <h3 className="font-semibold mb-2">Summary</h3>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-gray-600">Files Changed:</span>
            <span className="ml-2 font-medium">{data.summary.total_files_changed}</span>
          </div>
          <div>
            <span className="text-gray-600">Symbols Changed:</span>
            <span className="ml-2 font-medium">{data.summary.total_symbols_changed}</span>
          </div>
          {data.summary.commit && (
            <div className="col-span-2">
              <span className="text-gray-600">Commit:</span>
              <span className="ml-2 font-mono text-xs">{data.summary.commit.substring(0, 8)}</span>
            </div>
          )}
          {data.summary.commit_range && (
            <div className="col-span-2">
              <span className="text-gray-600">Range:</span>
              <span className="ml-2 font-mono text-xs">
                {data.summary.commit_range.base.substring(0, 8)}...
                {data.summary.commit_range.head.substring(0, 8)}
              </span>
            </div>
          )}
        </div>
      </Card>

      {/* Files Changed */}
      {data.files_changed.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">Files Changed ({data.files_changed.length})</h3>
          <div className="space-y-1">
            {data.files_changed.slice(0, 10).map((file, idx) => (
              <button
                key={idx}
                onClick={() => onFileSelect(file.path)}
                className="w-full rounded px-2 py-1 text-left text-sm hover:bg-gray-100 flex items-center gap-2"
              >
                {file.change_type === 'added' && <span className="text-green-600">+</span>}
                {file.change_type === 'modified' && <span className="text-blue-600">~</span>}
                {file.change_type === 'deleted' && <span className="text-red-600">-</span>}
                <FileCode className="h-3 w-3" />
                <span className="truncate">{file.path}</span>
                {file.additions !== undefined && file.deletions !== undefined && (
                  <span className="ml-auto text-xs text-gray-500">
                    +{file.additions} -{file.deletions}
                  </span>
                )}
              </button>
            ))}
            {data.files_changed.length > 10 && (
              <p className="text-xs text-gray-500 pl-2">
                and {data.files_changed.length - 10} more files...
              </p>
            )}
          </div>
        </Card>
      )}

      {/* Changed Symbols */}
      {data.changed_symbols.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">Changed Symbols ({data.changed_symbols.length})</h3>
          <div className="space-y-1">
            {data.changed_symbols.slice(0, 10).map((symbol, idx) => (
              <button
                key={idx}
                onClick={() => onFileSelect(symbol.file_path, symbol.line_number)}
                className="w-full rounded px-2 py-1 text-left text-sm hover:bg-gray-100"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    symbol.change_type === 'added' ? 'bg-green-100 text-green-700' :
                    symbol.change_type === 'modified' ? 'bg-blue-100 text-blue-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {symbol.change_type}
                  </span>
                  <span className="font-mono text-xs">{symbol.name}</span>
                  <span className="text-xs text-gray-500">({symbol.symbol_type})</span>
                  {symbol.is_public && (
                    <span className="ml-auto text-xs text-blue-600">public</span>
                  )}
                </div>
              </button>
            ))}
            {data.changed_symbols.length > 10 && (
              <p className="text-xs text-gray-500 pl-2">
                and {data.changed_symbols.length - 10} more symbols...
              </p>
            )}
          </div>
        </Card>
      )}

      {/* Dependency Impact */}
      <Card className="p-4">
        <h3 className="font-semibold mb-2">Dependency Impact</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Affected Symbols:</span>
            <span className="font-medium">{data.dependency_impact.affected_symbols}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Total Callers:</span>
            <span className="font-medium">{data.dependency_impact.graph_traversal.total_callers}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Total Callees:</span>
            <span className="font-medium">{data.dependency_impact.graph_traversal.total_callees}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Max Depth:</span>
            <span className="font-medium">{data.dependency_impact.graph_traversal.max_depth_reached}</span>
          </div>
          {data.dependency_impact.graph_traversal.truncated && (
            <p className="text-xs text-orange-600 mt-2">
              ⚠ Graph traversal was truncated due to complexity limits
            </p>
          )}
        </div>
      </Card>

      {/* API Impact */}
      {data.api_impact.total_endpoints_affected > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">
            API Impact ({data.api_impact.total_endpoints_affected} endpoints)
          </h3>
          <div className="space-y-1">
            {data.api_impact.affected_endpoints.slice(0, 5).map((endpoint, idx) => (
              <button
                key={idx}
                onClick={() => onFileSelect(endpoint.file_path)}
                className="w-full rounded px-2 py-1 text-left text-sm hover:bg-gray-100"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${
                    endpoint.directly_affected
                      ? 'bg-red-100 text-red-700'
                      : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {endpoint.method}
                  </span>
                  <span className="text-xs font-mono">{endpoint.route}</span>
                  {endpoint.directly_affected && (
                    <span className="ml-auto text-xs text-red-600">direct</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* Test Intelligence */}
      {data.test_intelligence.total_tests > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">
            Test Intelligence ({data.test_intelligence.total_tests} tests)
          </h3>
          <p className="text-xs text-gray-600 mb-2">
            Confidence: {data.test_intelligence.confidence}
          </p>
          <div className="space-y-1">
            {data.test_intelligence.relevant_tests.slice(0, 5).map((test, idx) => (
              <button
                key={idx}
                onClick={() => onFileSelect(test.test_file)}
                className="w-full rounded px-2 py-1 text-left text-sm hover:bg-gray-100"
              >
                <div className="text-xs">{test.test_file}</div>
                {test.test_name && (
                  <div className="text-xs text-gray-500">{test.test_name}</div>
                )}
                <div className="text-xs text-gray-500 mt-1">{test.relevance_reason}</div>
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* Workflow Impact */}
      {data.workflow_impact.total_workflows_affected > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">
            Workflow Impact ({data.workflow_impact.total_workflows_affected} workflows)
          </h3>
          <div className="space-y-2">
            {data.workflow_impact.affected_workflows.map((workflow, idx) => (
              <div key={idx} className="rounded border p-2 text-sm">
                <div className="font-medium">{workflow.workflow_name}</div>
                {workflow.affected_tasks && workflow.affected_tasks.length > 0 && (
                  <div className="mt-1 text-xs text-gray-600">
                    Affected tasks: {workflow.affected_tasks.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Evidence */}
      {data.evidence.key_evidence.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold mb-2">Key Evidence</h3>
          <ul className="list-disc space-y-1 pl-5 text-xs text-gray-700">
            {data.evidence.key_evidence.map((evidence, idx) => (
              <li key={idx}>{evidence}</li>
            ))}
          </ul>
        </Card>
      )}

      {/* Limitations */}
      {data.evidence.limitations.length > 0 && (
        <Card className="p-4 border-yellow-200 bg-yellow-50">
          <h3 className="font-semibold mb-2 text-yellow-900">Limitations</h3>
          <ul className="list-disc space-y-1 pl-5 text-xs text-yellow-800">
            {data.evidence.limitations.map((limitation, idx) => (
              <li key={idx}>{limitation}</li>
            ))}
          </ul>
        </Card>
      )}

      {/* LLM Analysis */}
      {data.llm_analysis && (
        <Card className="p-4 bg-blue-50 border-blue-200">
          <h3 className="font-semibold mb-2 text-blue-900">AI Analysis</h3>
          <p className="text-sm text-blue-800 mb-3">{data.llm_analysis.summary}</p>
          
          {data.llm_analysis.potential_issues.length > 0 && (
            <div className="mb-3">
              <h4 className="text-sm font-medium text-blue-900 mb-1">Potential Issues:</h4>
              <ul className="list-disc space-y-1 pl-5 text-xs text-blue-800">
                {data.llm_analysis.potential_issues.map((issue, idx) => (
                  <li key={idx}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {data.llm_analysis.recommendations.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-blue-900 mb-1">Recommendations:</h4>
              <ul className="list-disc space-y-1 pl-5 text-xs text-blue-800">
                {data.llm_analysis.recommendations.map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
