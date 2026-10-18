/**
 * Test Results Component - Phase 21
 * 
 * Integrates test-result intelligence into the developer workspace.
 * Features:
 * - Test run dashboard
 * - Test report import (JUnit XML, Normalized JSON)
 * - Failure investigation with classification and AI explanations
 * - Historical comparison and trend analysis
 */

'use client';

import { useState, useRef } from 'react';
import {
  useTestRuns,
  useTestRunDetail,
  useTestFailures,
  useImportTestResults,
  useExplainTestFailure,
  type RepositoryFile,
} from '@/lib/hooks';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Loader2,
  Upload,
  CheckCircle2,
  XCircle,
  AlertCircle,
  MinusCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  FileText,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import type {
  TestRunSummary,
  TestCaseDetail,
  FailureCorrelation,
  HistoricalTrend,
} from '@/types/test-results';

interface TestResultsProps {
  repositoryId: string;
  files: RepositoryFile[];
  onFileSelect?: (file: RepositoryFile, line?: number) => void;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const SUPPORTED_FORMATS = ['xml', 'json'];

export function TestResults({ repositoryId, files, onFileSelect }: TestResultsProps) {
  const [view, setView] = useState<'dashboard' | 'import'>('dashboard');
  const [selectedRun, setSelectedRun] = useState<TestRunSummary | null>(null);
  const [selectedTest, setSelectedTest] = useState<TestCaseDetail | null>(null);
  const [compareRunId, setCompareRunId] = useState<string | null>(null);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b bg-gray-50 px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Test Results</h3>
            <p className="text-sm text-gray-600">Import and analyze test execution results</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant={view === 'dashboard' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setView('dashboard')}
            >
              Dashboard
            </Button>
            <Button
              variant={view === 'import' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setView('import')}
            >
              <Upload className="mr-2 h-4 w-4" />
              Import
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {view === 'import' ? (
          <ImportTestResults repositoryId={repositoryId} onSuccess={() => setView('dashboard')} />
        ) : !selectedRun ? (
          <TestRunDashboard
            repositoryId={repositoryId}
            onSelectRun={setSelectedRun}
            onCompare={(runId) => setCompareRunId(runId)}
          />
        ) : (
          <TestRunDetails
            repositoryId={repositoryId}
            run={selectedRun}
            compareRunId={compareRunId}
            files={files}
            onBack={() => {
              setSelectedRun(null);
              setSelectedTest(null);
              setCompareRunId(null);
            }}
            onSelectTest={setSelectedTest}
            selectedTest={selectedTest}
            onFileSelect={onFileSelect}
          />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Import Test Results
// ============================================================================

function ImportTestResults({ repositoryId, onSuccess }: { repositoryId: string; onSuccess: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [commitSha, setCommitSha] = useState('');
  const [formatHint, setFormatHint] = useState<'auto' | 'junit_xml' | 'normalized_json'>('auto');
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const importMutation = useImportTestResults(repositoryId);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    setError(null);

    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Validate file size
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError(`File size exceeds 50MB limit (${(selectedFile.size / 1024 / 1024).toFixed(1)}MB)`);
      setFile(null);
      return;
    }

    // Validate file extension
    const extension = selectedFile.name.split('.').pop()?.toLowerCase();
    if (extension && !SUPPORTED_FORMATS.includes(extension)) {
      setError(`Unsupported file type: .${extension}. Supported: .xml, .json`);
      setFile(null);
      return;
    }

    setFile(selectedFile);
  };

  const handleImport = async () => {
    if (!file) return;

    setError(null);

    try {
      const content = await file.text();

      await importMutation.mutateAsync({
        report_content: content,
        format_hint: formatHint,
        commit_sha: commitSha || null,
      });

      // Success
      setFile(null);
      setCommitSha('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import test results');
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Card className="p-6">
        <h4 className="mb-4 text-lg font-semibold">Import Test Report</h4>

        {/* Format Information */}
        <div className="mb-6 rounded border border-blue-200 bg-blue-50 p-4 text-sm">
          <p className="font-medium text-blue-900">Supported Formats:</p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-blue-800">
            <li>JUnit XML (pytest, jest, and compatible frameworks)</li>
            <li>Normalized JSON (CodeTraceX format)</li>
          </ul>
          <p className="mt-3 text-blue-700">
            <strong>Size Limit:</strong> 50MB | <strong>Max Test Cases:</strong> 100,000
          </p>
        </div>

        {/* File Input */}
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium">Test Report File</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xml,.json"
            onChange={handleFileSelect}
            className="w-full cursor-pointer rounded border border-gray-300 bg-white p-2 text-sm file:mr-4 file:cursor-pointer file:rounded file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
          />
          {file && (
            <p className="mt-2 text-sm text-gray-600">
              Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </p>
          )}
        </div>

        {/* Format Hint */}
        <div className="mb-4">
          <label className="mb-2 block text-sm font-medium">Format (optional)</label>
          <select
            value={formatHint}
            onChange={(e) => setFormatHint(e.target.value as typeof formatHint)}
            className="w-full rounded border border-gray-300 p-2 text-sm"
          >
            <option value="auto">Auto-detect</option>
            <option value="junit_xml">JUnit XML</option>
            <option value="normalized_json">Normalized JSON</option>
          </select>
        </div>

        {/* Commit SHA */}
        <div className="mb-6">
          <label className="mb-2 block text-sm font-medium">Commit SHA (optional)</label>
          <Input
            value={commitSha}
            onChange={(e) => setCommitSha(e.target.value)}
            placeholder="abc123def456"
            className="font-mono text-sm"
          />
          <p className="mt-1 text-xs text-gray-500">
            Associate this test run with a commit for correlation analysis
          </p>
        </div>

        {/* Error Display */}
        {(error || importMutation.isError) && (
          <div className="mb-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {error || 'Import failed. Please check the file format and try again.'}
          </div>
        )}

        {/* Success Display */}
        {importMutation.isSuccess && (
          <div className="mb-4 rounded border border-green-200 bg-green-50 p-3 text-sm text-green-800">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              <span>
                Import successful!{' '}
                {importMutation.data.was_duplicate && '(Duplicate detected - existing run returned)'}
              </span>
            </div>
            <div className="mt-2">
              {importMutation.data.total_tests} tests: {importMutation.data.passed_tests} passed,{' '}
              {importMutation.data.failed_tests} failed
            </div>
          </div>
        )}

        {/* Import Button */}
        <Button
          onClick={handleImport}
          disabled={!file || importMutation.isPending}
          className="w-full"
        >
          {importMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Importing...
            </>
          ) : (
            <>
              <Upload className="mr-2 h-4 w-4" />
              Import Test Results
            </>
          )}
        </Button>
      </Card>

      {/* Information Card */}
      <Card className="p-4 text-sm text-gray-700">
        <p className="mb-2 font-medium">Important Notes:</p>
        <ul className="list-inside list-disc space-y-1">
          <li>Reports are never executed - only parsed and analyzed</li>
          <li>Duplicate imports are detected automatically and won't create duplicates</li>
          <li>Failure classifications are deterministic and evidence-based</li>
          <li>Commit association enables code change correlation</li>
        </ul>
      </Card>
    </div>
  );
}

// ============================================================================
// Test Run Dashboard
// ============================================================================

function TestRunDashboard({
  repositoryId,
  onSelectRun,
  onCompare,
}: {
  repositoryId: string;
  onSelectRun: (run: TestRunSummary) => void;
  onCompare: (runId: string) => void;
}) {
  const { data, isLoading, error } = useTestRuns(repositoryId, 50, 0);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        Failed to load test runs. Please check the backend connection.
      </div>
    );
  }

  if (!data || data.test_runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <FileText className="mb-4 h-16 w-16 text-gray-300" />
        <h4 className="mb-2 text-lg font-medium text-gray-700">No test runs yet</h4>
        <p className="text-sm text-gray-600">Import a test report to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-lg font-semibold">Test Runs ({data.total_count})</h4>
      </div>

      <div className="space-y-3">
        {data.test_runs.map((run) => (
          <Card key={run.id} className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="mb-2 flex items-center gap-3">
                  <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium">
                    {run.source_format}
                  </span>
                  {run.commit_sha && (
                    <span className="font-mono text-xs text-gray-600">{run.commit_sha}</span>
                  )}
                  <span className="text-xs text-gray-500">
                    {new Date(run.imported_at).toLocaleString()}
                  </span>
                </div>

                <div className="grid grid-cols-5 gap-4">
                  <TestCount
                    icon={CheckCircle2}
                    label="Passed"
                    count={run.passed_tests}
                    color="text-green-600"
                  />
                  <TestCount
                    icon={XCircle}
                    label="Failed"
                    count={run.failed_tests}
                    color="text-red-600"
                  />
                  <TestCount
                    icon={AlertCircle}
                    label="Error"
                    count={run.error_tests}
                    color="text-orange-600"
                  />
                  <TestCount
                    icon={MinusCircle}
                    label="Skipped"
                    count={run.skipped_tests}
                    color="text-gray-600"
                  />
                  {run.total_duration_ms !== null && (
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-gray-400" />
                      <div>
                        <div className="text-xs text-gray-600">Duration</div>
                        <div className="text-sm font-medium">
                          {(run.total_duration_ms / 1000).toFixed(1)}s
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {run.failed_tests > 0 && (
                  <div className="mt-3">
                    <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
                      <div
                        className="h-full bg-red-500"
                        style={{
                          width: `${(run.failed_tests / run.total_tests) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="ml-4 flex flex-col gap-2">
                <Button size="sm" onClick={() => onSelectRun(run)}>
                  View Details
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function TestCount({
  icon: Icon,
  label,
  count,
  color,
}: {
  icon: React.ElementType;
  label: string;
  count: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className={`h-4 w-4 ${color}`} />
      <div>
        <div className="text-xs text-gray-600">{label}</div>
        <div className="text-sm font-medium">{count}</div>
      </div>
    </div>
  );
}

// ============================================================================
// Test Run Details
// ============================================================================

function TestRunDetails({
  repositoryId,
  run,
  compareRunId,
  files,
  onBack,
  onSelectTest,
  selectedTest,
  onFileSelect,
}: {
  repositoryId: string;
  run: TestRunSummary;
  compareRunId: string | null;
  files: RepositoryFile[];
  onBack: () => void;
  onSelectTest: (test: TestCaseDetail | null) => void;
  selectedTest: TestCaseDetail | null;
  onFileSelect?: (file: RepositoryFile, line?: number) => void;
}) {
  const { data: details, isLoading, error } = useTestRunDetail(repositoryId, run.id);
  const {
    data: failures,
    isLoading: failuresLoading,
    error: failuresError,
  } = useTestFailures(repositoryId, run.id);

  if (isLoading || failuresLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error || failuresError) {
    return (
      <div>
        <Button variant="outline" size="sm" onClick={onBack} className="mb-4">
          ← Back to Dashboard
        </Button>
        <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Failed to load test run details. Please try again.
        </div>
      </div>
    );
  }

  if (!details || !failures) return null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Button variant="outline" size="sm" onClick={onBack}>
          ← Back to Dashboard
        </Button>
        <div className="text-sm text-gray-600">
          {new Date(details.imported_at).toLocaleString()}
        </div>
      </div>

      {/* Summary */}
      <Card className="p-4">
        <div className="grid grid-cols-5 gap-4">
          <TestCount
            icon={CheckCircle2}
            label="Passed"
            count={details.passed_tests}
            color="text-green-600"
          />
          <TestCount
            icon={XCircle}
            label="Failed"
            count={details.failed_tests}
            color="text-red-600"
          />
          <TestCount
            icon={AlertCircle}
            label="Error"
            count={details.error_tests}
            color="text-orange-600"
          />
          <TestCount
            icon={MinusCircle}
            label="Skipped"
            count={details.skipped_tests}
            color="text-gray-600"
          />
          {details.total_duration_ms !== null && (
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-gray-400" />
              <div>
                <div className="text-xs text-gray-600">Duration</div>
                <div className="text-sm font-medium">
                  {(details.total_duration_ms / 1000).toFixed(1)}s
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Failures */}
      {failures.failed_tests.length > 0 ? (
        <div>
          <h4 className="mb-3 text-lg font-semibold">Failures ({failures.total_failures})</h4>
          <FailureInvestigation
            repositoryId={repositoryId}
            failures={failures}
            selectedTest={selectedTest}
            onSelectTest={onSelectTest}
            files={files}
            onFileSelect={onFileSelect}
          />
        </div>
      ) : (
        <Card className="p-8 text-center">
          <CheckCircle2 className="mx-auto mb-3 h-12 w-12 text-green-500" />
          <h4 className="mb-2 text-lg font-medium text-green-700">All tests passed!</h4>
          <p className="text-sm text-gray-600">No failures to investigate</p>
        </Card>
      )}

      {/* Historical Trends */}
      {failures.trends.length > 0 && (
        <div>
          <h4 className="mb-3 text-lg font-semibold">Historical Trends</h4>
          <HistoricalComparison trends={failures.trends} />
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Failure Investigation
// ============================================================================

function FailureInvestigation({
  repositoryId,
  failures,
  selectedTest,
  onSelectTest,
  files,
  onFileSelect,
}: {
  repositoryId: string;
  failures: {
    failed_tests: TestCaseDetail[];
    correlations: FailureCorrelation[];
    trends: HistoricalTrend[];
  };
  selectedTest: TestCaseDetail | null;
  onSelectTest: (test: TestCaseDetail | null) => void;
  files: RepositoryFile[];
  onFileSelect?: (file: RepositoryFile, line?: number) => void;
}) {
  const [expandedTests, setExpandedTests] = useState<Set<string>>(new Set());

  const toggleExpand = (testId: string) => {
    const newExpanded = new Set(expandedTests);
    if (newExpanded.has(testId)) {
      newExpanded.delete(testId);
      if (selectedTest?.id === testId) {
        onSelectTest(null);
      }
    } else {
      newExpanded.add(testId);
    }
    setExpandedTests(newExpanded);
  };

  return (
    <div className="space-y-3">
      {failures.failed_tests.map((test) => {
        const isExpanded = expandedTests.has(test.id);
        const correlations = failures.correlations.filter((c) => c.test_case_id === test.id);
        const trends = failures.trends.filter((t) => t.test_name === test.full_name);

        return (
          <Card key={test.id} className="overflow-hidden">
            <button
              onClick={() => toggleExpand(test.id)}
              className="w-full p-4 text-left transition-colors hover:bg-gray-50"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    )}
                    <h5 className="font-medium">{test.test_name}</h5>
                  </div>
                  <div className="ml-6 mt-1 text-sm text-gray-600">{test.suite_name}</div>

                  {test.failure_classification && (
                    <div className="ml-6 mt-2 flex items-center gap-3">
                      <span className="rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-700">
                        {test.failure_classification}
                      </span>
                      {test.classification_confidence !== null && (
                        <span className="text-xs text-gray-600">
                          Confidence: {(test.classification_confidence * 100).toFixed(0)}%
                        </span>
                      )}
                      {test.duration_ms !== null && (
                        <span className="flex items-center gap-1 text-xs text-gray-600">
                          <Clock className="h-3 w-3" />
                          {test.duration_ms}ms
                        </span>
                      )}
                    </div>
                  )}

                  {test.failure_message && !isExpanded && (
                    <div className="ml-6 mt-2 truncate text-sm text-gray-700">
                      {test.failure_message}
                    </div>
                  )}
                </div>
              </div>
            </button>

            {isExpanded && (
              <div className="border-t bg-gray-50 p-4">
                <FailureDetails
                  repositoryId={repositoryId}
                  test={test}
                  correlations={correlations}
                  trends={trends}
                  files={files}
                  onFileSelect={onFileSelect}
                />
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// ============================================================================
// Failure Details
// ============================================================================

function FailureDetails({
  repositoryId,
  test,
  correlations,
  trends,
  files,
  onFileSelect,
}: {
  repositoryId: string;
  test: TestCaseDetail;
  correlations: FailureCorrelation[];
  trends: HistoricalTrend[];
  files: RepositoryFile[];
  onFileSelect?: (file: RepositoryFile, line?: number) => void;
}) {
  const [showExplanation, setShowExplanation] = useState(false);
  const explainMutation = useExplainTestFailure(repositoryId);

  const handleExplain = () => {
    setShowExplanation(true);
    if (!explainMutation.data) {
      explainMutation.mutate({
        test_case_id: test.id,
        include_correlations: true,
        include_trends: true,
      });
    }
  };

  return (
    <div className="space-y-4">
      {/* Failure Message */}
      {test.failure_message && (
        <div>
          <h6 className="mb-2 text-sm font-semibold">Failure Message</h6>
          <div className="rounded bg-red-50 p-3 font-mono text-sm text-red-900">
            {test.failure_message}
          </div>
        </div>
      )}

      {/* Stack Trace */}
      {test.failure_stacktrace && (
        <div>
          <h6 className="mb-2 text-sm font-semibold">Stack Trace</h6>
          <div className="max-h-64 overflow-y-auto rounded bg-gray-900 p-3 font-mono text-xs text-gray-100">
            <pre className="whitespace-pre-wrap">{test.failure_stacktrace}</pre>
          </div>
        </div>
      )}

      {/* Classification Evidence */}
      {test.classification_evidence && (
        <div>
          <h6 className="mb-2 text-sm font-semibold">Classification Evidence</h6>
          <div className="rounded border border-gray-300 bg-white p-3 text-sm text-gray-700">
            {test.classification_evidence}
          </div>
        </div>
      )}

      {/* Correlations */}
      {correlations.length > 0 && (
        <div>
          <h6 className="mb-2 text-sm font-semibold">Code Change Correlations</h6>
          <div className="space-y-2">
            {correlations.map((correlation, idx) => (
              <div key={idx} className="rounded border border-blue-200 bg-blue-50 p-3">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white">
                    {correlation.correlation_type}
                  </span>
                  <span className="text-xs text-blue-700">
                    Confidence: {correlation.confidence}
                  </span>
                </div>

                {correlation.changed_files.length > 0 && (
                  <div className="mb-2">
                    <div className="mb-1 text-xs font-medium text-blue-900">Changed Files:</div>
                    <div className="space-y-1">
                      {correlation.changed_files.map((filePath, fileIdx) => {
                        const file = files.find((f) => f.path === filePath);
                        return (
                          <button
                            key={fileIdx}
                            onClick={() => file && onFileSelect?.(file)}
                            disabled={!file || file.is_sensitive}
                            className="block w-full rounded bg-white px-2 py-1 text-left font-mono text-xs text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {filePath}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {correlation.evidence.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-medium text-blue-900">Evidence:</div>
                    <ul className="list-inside list-disc space-y-1 text-xs text-blue-800">
                      {correlation.evidence.map((evidence, evidenceIdx) => (
                        <li key={evidenceIdx}>{evidence}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trends */}
      {trends.length > 0 && (
        <div>
          <h6 className="mb-2 text-sm font-semibold">Historical Trends</h6>
          <div className="space-y-2">
            {trends.map((trend, idx) => (
              <div key={idx} className="rounded border border-orange-200 bg-orange-50 p-3">
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded bg-orange-600 px-2 py-1 text-xs font-medium text-white">
                    {trend.trend_type.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs text-orange-700">
                    {trend.runs_analyzed} runs analyzed
                  </span>
                </div>
                <div className="mb-2 text-sm text-orange-900">{trend.description}</div>
                {trend.evidence.length > 0 && (
                  <ul className="list-inside list-disc space-y-1 text-xs text-orange-800">
                    {trend.evidence.map((evidence, evidenceIdx) => (
                      <li key={evidenceIdx}>{evidence}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Explanation */}
      <div>
        <Button
          onClick={handleExplain}
          disabled={explainMutation.isPending}
          variant="outline"
          size="sm"
          className="w-full"
        >
          {explainMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Generating Explanation...
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              {explainMutation.data ? 'Refresh AI Explanation' : 'Generate AI Explanation'}
            </>
          )}
        </Button>

        {explainMutation.isError && (
          <div className="mt-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            Failed to generate explanation. LLM service may not be configured.
          </div>
        )}

        {explainMutation.data && showExplanation && (
          <div className="mt-3 space-y-3">
            <div className="rounded border border-purple-200 bg-purple-50 p-3">
              <h6 className="mb-2 text-sm font-semibold text-purple-900">Summary</h6>
              <p className="text-sm text-purple-800">{explainMutation.data.failure_summary}</p>
            </div>

            <div className="rounded border border-gray-300 bg-white p-3">
              <h6 className="mb-2 text-sm font-semibold">Potential Causes (Hypothesis)</h6>
              <p className="whitespace-pre-wrap text-sm text-gray-700">
                {explainMutation.data.potential_causes}
              </p>
            </div>

            <div className="rounded border border-gray-300 bg-white p-3">
              <h6 className="mb-2 text-sm font-semibold">Investigation Steps</h6>
              <p className="whitespace-pre-wrap text-sm text-gray-700">
                {explainMutation.data.investigation_steps}
              </p>
            </div>

            {explainMutation.data.related_changes && (
              <div className="rounded border border-gray-300 bg-white p-3">
                <h6 className="mb-2 text-sm font-semibold">Related Changes</h6>
                <p className="whitespace-pre-wrap text-sm text-gray-700">
                  {explainMutation.data.related_changes}
                </p>
              </div>
            )}

            <div className="rounded border border-yellow-200 bg-yellow-50 p-3">
              <h6 className="mb-2 text-sm font-semibold text-yellow-900">Uncertainty</h6>
              <p className="whitespace-pre-wrap text-sm text-yellow-800">
                {explainMutation.data.uncertainty}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Historical Comparison
// ============================================================================

function HistoricalComparison({ trends }: { trends: HistoricalTrend[] }) {
  const regressions = trends.filter((t) => t.trend_type === 'regression');
  const fixes = trends.filter((t) => t.trend_type === 'fixed');
  const flaky = trends.filter((t) => t.trend_type === 'potentially_flaky');
  const repeated = trends.filter((t) => t.trend_type === 'repeated_failure');

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {regressions.length > 0 && (
        <TrendCard
          icon={TrendingDown}
          title="Regressions"
          count={regressions.length}
          trends={regressions}
          color="red"
        />
      )}
      {fixes.length > 0 && (
        <TrendCard
          icon={TrendingUp}
          title="Fixes"
          count={fixes.length}
          trends={fixes}
          color="green"
        />
      )}
      {flaky.length > 0 && (
        <TrendCard
          icon={AlertTriangle}
          title="Potentially Flaky"
          count={flaky.length}
          trends={flaky}
          color="yellow"
        />
      )}
      {repeated.length > 0 && (
        <TrendCard
          icon={XCircle}
          title="Repeated Failures"
          count={repeated.length}
          trends={repeated}
          color="orange"
        />
      )}
    </div>
  );
}

function TrendCard({
  icon: Icon,
  title,
  count,
  trends,
  color,
}: {
  icon: React.ElementType;
  title: string;
  count: number;
  trends: HistoricalTrend[];
  color: 'red' | 'green' | 'yellow' | 'orange';
}) {
  const [expanded, setExpanded] = useState(false);

  const colorClasses = {
    red: 'bg-red-50 border-red-200 text-red-900',
    green: 'bg-green-50 border-green-200 text-green-900',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-900',
    orange: 'bg-orange-50 border-orange-200 text-orange-900',
  };

  const iconColorClasses = {
    red: 'text-red-600',
    green: 'text-green-600',
    yellow: 'text-yellow-600',
    orange: 'text-orange-600',
  };

  return (
    <Card className={`overflow-hidden border ${colorClasses[color]}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 text-left transition-colors hover:opacity-80"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={`h-5 w-5 ${iconColorClasses[color]}`} />
            <div>
              <h6 className="font-semibold">{title}</h6>
              <p className="text-sm opacity-80">{count} tests</p>
            </div>
          </div>
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="space-y-2 border-t p-4">
          {trends.map((trend, idx) => (
            <div key={idx} className="rounded bg-white p-3">
              <div className="mb-1 font-mono text-xs">{trend.test_name}</div>
              <div className="text-sm">{trend.description}</div>
              {trend.evidence.length > 0 && (
                <ul className="mt-2 list-inside list-disc space-y-1 text-xs opacity-80">
                  {trend.evidence.map((evidence, evidenceIdx) => (
                    <li key={evidenceIdx}>{evidence}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
