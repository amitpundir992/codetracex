'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { analyzeRepository, APIError } from '@/lib/api';
import { RepositoryAnalysisResponse } from '@/types/repository';
import { Loader2, AlertCircle, GitBranch, FileCode, HardDrive } from 'lucide-react';

export default function RepositoryPage() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RepositoryAnalysisResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Clear previous state
    setError(null);
    setAnalysis(null);
    
    // Validate input
    if (!url.trim()) {
      setError('Please enter a GitHub repository URL');
      return;
    }
    
    setLoading(true);
    setLoadingStage('Downloading repository...');
    
    try {
      // Simulate stage updates for better UX
      setTimeout(() => setLoadingStage('Scanning files...'), 2000);
      setTimeout(() => setLoadingStage('Analyzing code structure...'), 4000);
      
      const result = await analyzeRepository(url.trim());
      setAnalysis(result);
      setLoadingStage('');
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.detail || err.message);
      } else {
        setError('An unexpected error occurred');
      }
      setLoadingStage('');
    } finally {
      setLoading(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Header */}
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <div className="p-3 bg-primary/10 rounded-full">
                <GitBranch className="w-12 h-12 text-primary" />
              </div>
            </div>
            <h1 className="text-4xl font-bold tracking-tight">CodeTraceX</h1>
            <p className="text-xl text-muted-foreground">
              Understand your codebase. Trace its dependencies. Predict its impact.
            </p>
          </div>

          {/* Input Form */}
          <Card>
            <CardHeader>
              <CardTitle>Analyze Repository</CardTitle>
              <CardDescription>
                Enter a GitHub repository URL to scan and analyze its files
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    type="text"
                    placeholder="https://github.com/owner/repository"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={loading}
                    className="flex-1"
                  />
                  <Button type="submit" disabled={loading}>
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      'Analyze Repository'
                    )}
                  </Button>
                </div>
                {loadingStage && (
                  <p className="text-sm text-muted-foreground text-center">
                    {loadingStage}
                  </p>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Error State */}
          {error && (
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-destructive mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-destructive mb-1">Error</h3>
                    <p className="text-sm text-muted-foreground">{error}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Analysis Results */}
          {analysis && (
            <div className="space-y-6">
              {/* Repository Summary */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <GitBranch className="h-5 w-5" />
                    Repository Analysis
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <h2 className="text-2xl font-bold">{analysis.repository}</h2>
                    <p className="text-sm text-muted-foreground">
                      Status: {analysis.status}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="p-4 bg-slate-100 dark:bg-slate-800 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <FileCode className="h-4 w-4 text-primary" />
                        <h3 className="text-sm font-semibold text-muted-foreground">
                          Files Analyzed
                        </h3>
                      </div>
                      <p className="text-2xl font-bold">{analysis.total_files.toLocaleString()}</p>
                    </div>

                    <div className="p-4 bg-slate-100 dark:bg-slate-800 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <HardDrive className="h-4 w-4 text-primary" />
                        <h3 className="text-sm font-semibold text-muted-foreground">
                          Repository Size
                        </h3>
                      </div>
                      <p className="text-2xl font-bold">{formatBytes(analysis.total_size_bytes)}</p>
                    </div>

                    <div className="p-4 bg-slate-100 dark:bg-slate-800 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <FileCode className="h-4 w-4 text-primary" />
                        <h3 className="text-sm font-semibold text-muted-foreground">
                          Languages
                        </h3>
                      </div>
                      <p className="text-2xl font-bold">{Object.keys(analysis.languages).length}</p>
                    </div>
                  </div>

                  {analysis.note && (
                    <p className="text-sm text-muted-foreground italic">
                      {analysis.note}
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Language Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle>Language Distribution</CardTitle>
                  <CardDescription>
                    Number of files per programming language
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Object.entries(analysis.languages)
                      .sort(([, a], [, b]) => b - a)
                      .map(([language, count]) => (
                        <div key={language} className="p-3 bg-slate-100 dark:bg-slate-800 rounded">
                          <p className="text-sm font-semibold">{language}</p>
                          <p className="text-2xl font-bold text-primary">{count}</p>
                          <p className="text-xs text-muted-foreground">
                            {((count / analysis.total_files) * 100).toFixed(1)}%
                          </p>
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>

              {/* Phase 3: Static Analysis Summary */}
              {analysis.analysis_summary && (
                <Card>
                  <CardHeader>
                    <CardTitle>Static Code Analysis</CardTitle>
                    <CardDescription>
                      Deterministic code structure analysis
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                      <div className="p-4 bg-blue-50 dark:bg-blue-950 rounded-lg">
                        <p className="text-sm font-semibold text-blue-900 dark:text-blue-100">
                          Analyzed Files
                        </p>
                        <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                          {analysis.analysis_summary.analyzed_files}
                        </p>
                        <p className="text-xs text-blue-700 dark:text-blue-300">
                          of {analysis.analysis_summary.total_files} total
                        </p>
                      </div>

                      <div className="p-4 bg-purple-50 dark:bg-purple-950 rounded-lg">
                        <p className="text-sm font-semibold text-purple-900 dark:text-purple-100">
                          Symbols Extracted
                        </p>
                        <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                          {analysis.analysis_summary.total_symbols}
                        </p>
                        <p className="text-xs text-purple-700 dark:text-purple-300">
                          functions, classes, methods
                        </p>
                      </div>

                      <div className="p-4 bg-green-50 dark:bg-green-950 rounded-lg">
                        <p className="text-sm font-semibold text-green-900 dark:text-green-100">
                          Imports
                        </p>
                        <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                          {analysis.analysis_summary.total_imports}
                        </p>
                        <p className="text-xs text-green-700 dark:text-green-300">
                          dependencies detected
                        </p>
                      </div>

                      <div className="p-4 bg-orange-50 dark:bg-orange-950 rounded-lg">
                        <p className="text-sm font-semibold text-orange-900 dark:text-orange-100">
                          Function Calls
                        </p>
                        <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                          {analysis.analysis_summary.total_calls}
                        </p>
                        <p className="text-xs text-orange-700 dark:text-orange-300">
                          relationships found
                        </p>
                      </div>
                    </div>

                    {/* Symbol Types Breakdown */}
                    {Object.keys(analysis.analysis_summary.symbols_by_type).length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold mb-3">Symbol Types</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          {Object.entries(analysis.analysis_summary.symbols_by_type)
                            .sort(([, a], [, b]) => b - a)
                            .map(([type, count]) => (
                              <div key={type} className="p-3 bg-slate-100 dark:bg-slate-800 rounded">
                                <p className="text-xs font-medium text-muted-foreground capitalize">
                                  {type}
                                </p>
                                <p className="text-xl font-bold">{count}</p>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Phase 3: Extracted Symbols Preview */}
              {analysis.symbols && analysis.symbols.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Extracted Symbols</CardTitle>
                    <CardDescription>
                      Functions, classes, and methods found in the codebase (showing up to 50)
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {analysis.symbols.map((symbol, index) => (
                        <div
                          key={index}
                          className="p-3 bg-slate-50 dark:bg-slate-900 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-semibold text-sm">
                                  {symbol.name}
                                </span>
                                <span className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded">
                                  {symbol.type}
                                </span>
                                <span className="text-xs text-muted-foreground">
                                  {symbol.language}
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1 font-mono">
                                {symbol.file} : Lines {symbol.start_line}-{symbol.end_line}
                              </p>
                              {symbol.parent && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  Parent: <span className="font-mono">{symbol.parent}</span>
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Files List */}
              <Card>
                <CardHeader>
                  <CardTitle>Files</CardTitle>
                  <CardDescription>
                    Showing {analysis.files_returned} of {analysis.total_files} files
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {analysis.files.map((file, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-900 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-mono truncate">{file.path}</p>
                          <div className="flex items-center gap-4 mt-1">
                            {file.language && (
                              <span className="text-xs text-muted-foreground">
                                {file.language}
                              </span>
                            )}
                            {file.lines !== null && (
                              <span className="text-xs text-muted-foreground">
                                {file.lines} lines
                              </span>
                            )}
                            <span className="text-xs text-muted-foreground">
                              {formatBytes(file.size_bytes)}
                            </span>
                            {file.is_sensitive && (
                              <span className="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded">
                                Sensitive
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
