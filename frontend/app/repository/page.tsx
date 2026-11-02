'use client';

import { useState } from 'react';
import { RepositoryAnalysisResponse } from '@/types/repository';
import { analyzeRepository, APIError } from '@/lib/api';
import RepositoryInput from '@/components/RepositoryInput';
import AnalysisSummary from '@/components/AnalysisSummary';
import ChatAssistant from '@/components/ChatAssistant';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import GitHistory from '@/components/GitHistory';
import ApiExplorer from '@/components/ApiExplorer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { FileCode, GitBranch, Code2, History } from 'lucide-react';

export default function RepositoryPage() {
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RepositoryAnalysisResponse | null>(null);

  const handleSubmit = async (url: string) => {
    setError(null);
    setAnalysis(null);
    setLoading(true);
    setLoadingStage('Downloading repository...');
    
    try {
      setTimeout(() => setLoadingStage('Scanning files...'), 2000);
      setTimeout(() => setLoadingStage('Analyzing code structure...'), 4000);
      setTimeout(() => setLoadingStage('Generating embeddings...'), 6000);
      
      const result = await analyzeRepository(url);
      setAnalysis(result);
      setLoadingStage('');
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.detail || err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
      setLoadingStage('');
    } finally {
      setLoading(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="container mx-auto px-4 py-8 lg:py-12">
        <div className="max-w-7xl mx-auto space-y-8">
          {/* Input Section */}
          <RepositoryInput
            onSubmit={handleSubmit}
            loading={loading}
            loadingStage={loadingStage}
            error={error}
          />

          {/* Analysis Results */}
          {analysis && (
            <div className="space-y-8 animate-in fade-in duration-500">
              {/* Summary */}
              <AnalysisSummary
                repository={analysis.repository}
                status={analysis.status}
                totalFiles={analysis.total_files}
                totalSize={analysis.total_size_bytes}
                languages={analysis.languages}
                repositoryId={analysis.repository_id}
                analysisSummary={analysis.analysis_summary}
              />

              {/* Tabbed Content */}
              <Tabs defaultValue="files" className="w-full">
                <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4 h-auto">
                  <TabsTrigger value="files" className="flex items-center gap-2">
                    <FileCode className="w-4 h-4" />
                    <span className="hidden sm:inline">Files</span>
                    <span className="sm:hidden">Files</span>
                  </TabsTrigger>
                  <TabsTrigger value="symbols" className="flex items-center gap-2">
                    <Code2 className="w-4 h-4" />
                    <span className="hidden sm:inline">Symbols</span>
                    <span className="sm:hidden">Code</span>
                  </TabsTrigger>
                  {analysis.repository_id && (
                    <>
                      <TabsTrigger value="api" className="flex items-center gap-2">
                        <GitBranch className="w-4 h-4" />
                        <span className="hidden sm:inline">API</span>
                        <span className="sm:hidden">API</span>
                      </TabsTrigger>
                      <TabsTrigger value="history" className="flex items-center gap-2">
                        <History className="w-4 h-4" />
                        <span className="hidden sm:inline">History</span>
                        <span className="sm:hidden">Git</span>
                      </TabsTrigger>
                    </>
                  )}
                </TabsList>

                {/* Files Tab */}
                <TabsContent value="files" className="mt-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Repository Files</CardTitle>
                      <CardDescription>
                        Showing {analysis.files_returned} of {analysis.total_files} files
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-1 max-h-[600px] overflow-y-auto">
                        {analysis.files.map((file, index) => (
                          <div
                            key={index}
                            className="group flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
                          >
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-mono truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                {file.path}
                              </p>
                              <div className="flex items-center gap-3 mt-1">
                                {file.language && (
                                  <span className="text-xs px-2 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">
                                    {file.language}
                                  </span>
                                )}
                                {file.lines !== null && (
                                  <span className="text-xs text-slate-500">
                                    {file.lines} lines
                                  </span>
                                )}
                                <span className="text-xs text-slate-500">
                                  {formatBytes(file.size_bytes)}
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* Symbols Tab */}
                <TabsContent value="symbols" className="mt-6">
                  {analysis.symbols && analysis.symbols.length > 0 ? (
                    <Card>
                      <CardHeader>
                        <CardTitle>Code Symbols</CardTitle>
                        <CardDescription>
                          {analysis.symbols.length} functions, classes, and methods extracted
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2 max-h-[600px] overflow-y-auto">
                          {analysis.symbols.map((symbol, index) => (
                            <div
                              key={index}
                              className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            >
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono font-semibold text-sm">{symbol.name}</span>
                                <span className="text-xs px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded">
                                  {symbol.type}
                                </span>
                                <span className="text-xs text-slate-500">{symbol.language}</span>
                              </div>
                              <p className="text-xs text-slate-500 mt-1 font-mono">
                                {symbol.file} : {symbol.start_line}-{symbol.end_line}
                              </p>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ) : (
                    <Card>
                      <CardContent className="py-12 text-center">
                        <Code2 className="w-12 h-12 mx-auto mb-4 text-slate-400" />
                        <p className="text-slate-500">No symbols extracted yet</p>
                      </CardContent>
                    </Card>
                  )}
                </TabsContent>

                {/* API Tab */}
                {analysis.repository_id && (
                  <TabsContent value="api" className="mt-6">
                    <Card>
                      <CardHeader>
                        <CardTitle>API Endpoints</CardTitle>
                        <CardDescription>
                          REST endpoints detected through static analysis
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <ApiExplorer repositoryId={analysis.repository_id} />
                      </CardContent>
                    </Card>
                  </TabsContent>
                )}

                {/* History Tab */}
                {analysis.repository_id && (
                  <TabsContent value="history" className="mt-6">
                    <GitHistory repositoryId={analysis.repository_id} />
                  </TabsContent>
                )}
              </Tabs>
            </div>
          )}
        </div>
      </div>

      {/* AI Chat Assistant */}
      {analysis?.repository_id && (
        <ChatAssistant
          repositoryId={analysis.repository_id}
          repositoryName={analysis.repository}
        />
      )}
    </div>
  );
}
