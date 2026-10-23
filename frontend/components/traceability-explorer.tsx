/**
 * Traceability Explorer Component - Phase 23
 * 
 * Provides UI for Phase 22 test-to-code traceability:
 * - Source file → tests
 * - Symbol → tests
 * - Test → source files
 */

'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Search, FileCode, FlaskConical, AlertCircle, CheckCircle2 } from 'lucide-react';
import {
  useSourceToTests,
  useSymbolToTests,
  useTestToSources,
} from '@/lib/hooks/use-traceability';
import type { RepositoryFile } from '@/lib/hooks';
import type { AffectedTest, RelatedSourceFile } from '@/types/traceability';

interface TraceabilityExplorerProps {
  repositoryId: string;
  files: RepositoryFile[];
  onFileSelect: (file: RepositoryFile, line?: number) => void;
}

type ExplorerMode = 'source-to-tests' | 'symbol-to-tests' | 'test-to-sources';

export function TraceabilityExplorer({
  repositoryId,
  files,
  onFileSelect,
}: TraceabilityExplorerProps) {
  const [mode, setMode] = useState<ExplorerMode>('source-to-tests');
  const [sourceFile, setSourceFile] = useState('');
  const [symbolName, setSymbolName] = useState('');
  const [symbolFilePath, setSymbolFilePath] = useState('');
  const [testFile, setTestFile] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Query hooks - disabled until user clicks Search
  const [enabledQueries, setEnabledQueries] = useState({
    sourceToTests: false,
    symbolToTests: false,
    testToSources: false,
  });

  const sourceToTestsQuery = useSourceToTests(
    repositoryId,
    { source_file: sourceFile }
  );

  const symbolToTestsQuery = useSymbolToTests(
    repositoryId,
    { symbol_name: symbolName, file_path: symbolFilePath || undefined }
  );

  const testToSourcesQuery = useTestToSources(
    repositoryId,
    { test_file: testFile }
  );

  // Disable queries initially
  sourceToTestsQuery.refetch = sourceToTestsQuery.refetch;
  symbolToTestsQuery.refetch = symbolToTestsQuery.refetch;
  testToSourcesQuery.refetch = testToSourcesQuery.refetch;

  const handleSearch = () => {
    if (mode === 'source-to-tests' && sourceFile.trim()) {
      sourceToTestsQuery.refetch();
    } else if (mode === 'symbol-to-tests' && symbolName.trim()) {
      symbolToTestsQuery.refetch();
    } else if (mode === 'test-to-sources' && testFile.trim()) {
      testToSourcesQuery.refetch();
    }
  };

  const selectFile = (path: string, line?: number) => {
    const file = files.find((f) => f.path === path);
    if (file && !file.is_sensitive) {
      onFileSelect(file, line);
    }
  };

  const getConfidenceColor = (confidence: string) => {
    switch (confidence.toLowerCase()) {
      case 'high':
        return 'text-green-700 bg-green-100 border-green-300';
      case 'medium':
        return 'text-yellow-700 bg-yellow-100 border-yellow-300';
      case 'low':
        return 'text-orange-700 bg-orange-100 border-orange-300';
      default:
        return 'text-gray-700 bg-gray-100 border-gray-300';
    }
  };

  const getConfidenceIcon = (confidence: string) => {
    switch (confidence.toLowerCase()) {
      case 'high':
        return <CheckCircle2 className="h-4 w-4" />;
      case 'medium':
      case 'low':
        return <AlertCircle className="h-4 w-4" />;
      default:
        return null;
    }
  };

  // Filter files for autocomplete
  const filteredFiles = searchQuery
    ? files.filter((f) => f.path.toLowerCase().includes(searchQuery.toLowerCase()))
    : [];

  const testFiles = files.filter((f) => {
    const path = f.path.toLowerCase();
    return path.includes('test') || path.includes('spec');
  });

  const sourceFiles = files.filter((f) => {
    const path = f.path.toLowerCase();
    return !path.includes('test') && !path.includes('spec');
  });

  const renderSourceToTests = () => {
    const { data, isLoading, error } = sourceToTestsQuery;

    return (
      <div className="space-y-4">
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3">Find tests for a source file</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1">Source File Path</label>
              <Input
                placeholder="e.g., src/services/user_service.py"
                value={sourceFile}
                onChange={(e) => setSourceFile(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSearch();
                  }
                }}
              />
              <p className="text-xs text-gray-500 mt-1">
                Enter the full path of a source file to find related tests
              </p>
            </div>

            {searchQuery && filteredFiles.length > 0 && (
              <div className="max-h-32 overflow-y-auto border rounded p-2 space-y-1">
                {filteredFiles.slice(0, 10).map((file) => (
                  <button
                    key={file.id}
                    type="button"
                    onClick={() => {
                      setSourceFile(file.path);
                      setSearchQuery('');
                    }}
                    className="block w-full text-left text-xs p-1 hover:bg-gray-100 rounded"
                  >
                    {file.path}
                  </button>
                ))}
              </div>
            )}

            <Button
              onClick={handleSearch}
              disabled={!sourceFile.trim() || isLoading}
              className="w-full"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Find Related Tests
                </>
              )}
            </Button>
          </div>
        </Card>

        {error && (
          <Card className="p-4 border-red-200 bg-red-50">
            <p className="text-sm text-red-700">
              {error instanceof Error ? error.message : 'Failed to get traceability data'}
            </p>
          </Card>
        )}

        {data && (
          <Card className="p-4">
            <div className="mb-3">
              <h3 className="text-sm font-semibold mb-1">Results for: {data.source_file}</h3>
              <p className="text-xs text-gray-600">
                Found {data.total_related_tests} related test{data.total_related_tests !== 1 ? 's' : ''}
              </p>
            </div>

            {data.total_related_tests === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <FlaskConical className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                <p className="text-sm">No related tests found</p>
                <p className="text-xs mt-1">
                  This does not mean the code is untested. Tests may exist but were not detected
                  by static analysis.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {data.related_tests.map((test: AffectedTest, index: number) => (
                  <div
                    key={`${test.test_file}-${test.test_name || index}`}
                    className="border rounded p-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <button
                        type="button"
                        onClick={() => selectFile(test.test_file)}
                        className="text-sm font-medium text-blue-700 hover:underline text-left"
                      >
                        <FileCode className="h-4 w-4 inline mr-1" />
                        {test.test_file}
                      </button>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium border flex items-center gap-1 ${getConfidenceColor(
                          test.confidence
                        )}`}
                      >
                        {getConfidenceIcon(test.confidence)}
                        {test.confidence}
                      </span>
                    </div>

                    {test.test_name && (
                      <div className="text-xs text-gray-600 mb-2">
                        Test: <code className="bg-gray-100 px-1 rounded">{test.test_name}</code>
                      </div>
                    )}

                    <div className="text-xs text-gray-600 mb-2">
                      <span className="font-medium">Coverage Type:</span> {test.coverage_type}
                    </div>

                    {test.evidence && test.evidence.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-gray-700 mb-1">Evidence:</p>
                        <ul className="list-disc list-inside space-y-1">
                          {test.evidence.map((ev, i) => (
                            <li key={i} className="text-xs text-gray-600">
                              {ev}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {test.changed_symbols && test.changed_symbols.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-gray-700 mb-1">Related Symbols:</p>
                        <div className="flex flex-wrap gap-1">
                          {test.changed_symbols.map((symbol, i) => (
                            <span
                              key={i}
                              className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded"
                            >
                              {symbol}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    );
  };

  const renderSymbolToTests = () => {
    const { data, isLoading, error } = symbolToTestsQuery;

    return (
      <div className="space-y-4">
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3">Find tests for a symbol</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1">Symbol Name *</label>
              <Input
                placeholder="e.g., create_user"
                value={symbolName}
                onChange={(e) => setSymbolName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSearch();
                  }
                }}
              />
            </div>

            <div>
              <label className="block text-xs font-medium mb-1">
                File Path (optional, for disambiguation)
              </label>
              <Input
                placeholder="e.g., src/services/user_service.py"
                value={symbolFilePath}
                onChange={(e) => setSymbolFilePath(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSearch();
                  }
                }}
              />
              <p className="text-xs text-gray-500 mt-1">
                If the symbol appears in multiple files, specify the file path
              </p>
            </div>

            <Button
              onClick={handleSearch}
              disabled={!symbolName.trim() || isLoading}
              className="w-full"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Find Related Tests
                </>
              )}
            </Button>
          </div>
        </Card>

        {error && (
          <Card className="p-4 border-red-200 bg-red-50">
            <p className="text-sm text-red-700">
              {error instanceof Error ? error.message : 'Failed to get traceability data'}
            </p>
          </Card>
        )}

        {data && (
          <Card className="p-4">
            <div className="mb-3">
              <h3 className="text-sm font-semibold mb-1">
                Results for: <code className="bg-gray-100 px-1 rounded">{data.symbol_name}</code>
              </h3>
              {data.file_path && (
                <p className="text-xs text-gray-600">In file: {data.file_path}</p>
              )}
              <p className="text-xs text-gray-600 mt-1">
                Found {data.total_related_tests} related test{data.total_related_tests !== 1 ? 's' : ''}
              </p>
            </div>

            {data.total_related_tests === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <FlaskConical className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                <p className="text-sm">No related tests found</p>
                <p className="text-xs mt-1">
                  This symbol may not have direct test coverage, or tests exist but were not detected.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {data.related_tests.map((test: AffectedTest, index: number) => (
                  <div
                    key={`${test.test_file}-${test.test_name || index}`}
                    className="border rounded p-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <button
                        type="button"
                        onClick={() => selectFile(test.test_file)}
                        className="text-sm font-medium text-blue-700 hover:underline text-left"
                      >
                        <FileCode className="h-4 w-4 inline mr-1" />
                        {test.test_file}
                      </button>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium border flex items-center gap-1 ${getConfidenceColor(
                          test.confidence
                        )}`}
                      >
                        {getConfidenceIcon(test.confidence)}
                        {test.confidence}
                      </span>
                    </div>

                    {test.test_name && (
                      <div className="text-xs text-gray-600 mb-2">
                        Test: <code className="bg-gray-100 px-1 rounded">{test.test_name}</code>
                      </div>
                    )}

                    <div className="text-xs text-gray-600 mb-2">
                      <span className="font-medium">Coverage Type:</span> {test.coverage_type}
                    </div>

                    {test.evidence && test.evidence.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-gray-700 mb-1">Evidence:</p>
                        <ul className="list-disc list-inside space-y-1">
                          {test.evidence.map((ev, i) => (
                            <li key={i} className="text-xs text-gray-600">
                              {ev}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    );
  };

  const renderTestToSources = () => {
    const { data, isLoading, error } = testToSourcesQuery;

    return (
      <div className="space-y-4">
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-3">Find source files for a test</h3>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1">Test File Path</label>
              <Input
                placeholder="e.g., tests/test_user_service.py"
                value={testFile}
                onChange={(e) => setTestFile(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSearch();
                  }
                }}
              />
              <p className="text-xs text-gray-500 mt-1">
                Enter the full path of a test file to find related source files
              </p>
            </div>

            <Button
              onClick={handleSearch}
              disabled={!testFile.trim() || isLoading}
              className="w-full"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Find Related Sources
                </>
              )}
            </Button>
          </div>
        </Card>

        {error && (
          <Card className="p-4 border-red-200 bg-red-50">
            <p className="text-sm text-red-700">
              {error instanceof Error ? error.message : 'Failed to get traceability data'}
            </p>
          </Card>
        )}

        {data && (
          <Card className="p-4">
            <div className="mb-3">
              <h3 className="text-sm font-semibold mb-1">Results for: {data.test_file}</h3>
              <p className="text-xs text-gray-600">
                Found {data.total_related_sources} related source file
                {data.total_related_sources !== 1 ? 's' : ''}
              </p>
            </div>

            {data.total_related_sources === 0 ? (
              <div className="text-center py-6 text-gray-500">
                <FileCode className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                <p className="text-sm">No related source files found</p>
                <p className="text-xs mt-1">
                  This test may not have clear static relationships to source code.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {data.related_sources.map((source: RelatedSourceFile, index: number) => (
                  <div
                    key={`${source.source_file}-${index}`}
                    className="border rounded p-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <button
                        type="button"
                        onClick={() => selectFile(source.source_file)}
                        className="text-sm font-medium text-blue-700 hover:underline text-left"
                      >
                        <FileCode className="h-4 w-4 inline mr-1" />
                        {source.source_file}
                      </button>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium border flex items-center gap-1 ${getConfidenceColor(
                          source.confidence
                        )}`}
                      >
                        {getConfidenceIcon(source.confidence)}
                        {source.confidence}
                      </span>
                    </div>

                    <div className="text-xs text-gray-600 mb-2">
                      <span className="font-medium">Relationship:</span> {source.relationship_type}
                    </div>

                    {source.evidence && source.evidence.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-gray-700 mb-1">Evidence:</p>
                        <ul className="list-disc list-inside space-y-1">
                          {source.evidence.map((ev, i) => (
                            <li key={i} className="text-xs text-gray-600">
                              {ev}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {source.imported_symbols && source.imported_symbols.length > 0 && (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-gray-700 mb-1">Imported Symbols:</p>
                        <div className="flex flex-wrap gap-1">
                          {source.imported_symbols.map((symbol, i) => (
                            <span
                              key={i}
                              className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded"
                            >
                              {symbol}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    );
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Mode Selection */}
      <div className="border-b bg-white p-4">
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={mode === 'source-to-tests' ? 'default' : 'outline'}
            onClick={() => setMode('source-to-tests')}
          >
            Source → Tests
          </Button>
          <Button
            size="sm"
            variant={mode === 'symbol-to-tests' ? 'default' : 'outline'}
            onClick={() => setMode('symbol-to-tests')}
          >
            Symbol → Tests
          </Button>
          <Button
            size="sm"
            variant={mode === 'test-to-sources' ? 'default' : 'outline'}
            onClick={() => setMode('test-to-sources')}
          >
            Test → Sources
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {mode === 'source-to-tests' && renderSourceToTests()}
        {mode === 'symbol-to-tests' && renderSymbolToTests()}
        {mode === 'test-to-sources' && renderTestToSources()}
      </div>
    </div>
  );
}
