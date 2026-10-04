/**
 * Repository Dashboard - Phase 17
 * 
 * Unified workspace for repository investigation.
 * Shows repository metadata, analysis status, and provides
 * navigation to all exploration features.
 */

'use client';

import { useEffect, useState } from 'react';
import {
  ApiRequestError,
  useRepository,
  useLatestAnalysis,
  useLatestJobForRepository,
  useStartAnalysis,
} from '@/lib/hooks';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, GitBranch, FileCode, Code2, Box, Workflow, GitCommit } from 'lucide-react';
import Link from 'next/link';

export default function RepositoryDashboardPage({ params }: { params: { id: string } }) {
  const { id } = params;
  
  const { data: repository, isLoading: repoLoading, error: repoError } = useRepository(id);
  const {
    data: analysis,
    isLoading: analysisLoading,
    error: analysisError,
    refetch: refetchAnalysis,
  } = useLatestAnalysis(id);
  const { data: job, error: jobError } = useLatestJobForRepository(id);
  const startAnalysis = useStartAnalysis();
  const [startError, setStartError] = useState<string | null>(null);

  useEffect(() => {
    if (job?.status === 'completed') void refetchAnalysis();
  }, [job?.status, refetchAnalysis]);

  const handleStartAnalysis = async () => {
    if (!repository) return;
    setStartError(null);
    try {
      await startAnalysis.mutateAsync(repository.github_url);
    } catch (error) {
      setStartError(error instanceof Error ? error.message : 'Unable to start analysis.');
    }
  };

  if (repoLoading || analysisLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (repoError) {
    const notFound = repoError instanceof ApiRequestError && repoError.status === 404;
    return (
      <div className="container mx-auto p-8" role="alert">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">
            {notFound ? 'Repository Not Found' : 'Repository Unavailable'}
          </h1>
          <p className="mb-4 text-gray-600">
            {notFound
              ? 'The requested repository could not be found.'
              : repoError instanceof ApiRequestError
                ? repoError.message
                : 'Unable to reach the backend. Please try again.'}
          </p>
          <Link href="/"><Button>Back to Home</Button></Link>
        </div>
      </div>
    );
  }

  if (!repository) {
    return (
      <div className="container mx-auto p-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Repository Not Found</h1>
          <Link href="/">
            <Button>Back to Home</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">{repository.name}</h1>
              <p className="text-gray-600 mt-1">{repository.full_name}</p>
            </div>
            <div className="flex gap-2">
              <Link href={`/repositories/${id}/workspace`}>
                <Button size="lg">Open Workspace</Button>
              </Link>
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Repository Info */}
          <Card>
            <CardHeader>
              <CardTitle>Repository Info</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2 text-sm">
                <GitBranch className="h-4 w-4 text-gray-500" />
                <span className="text-gray-600">Branch:</span>
                <span className="font-medium">{repository.default_branch || 'Unknown'}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-600">Language:</span>
                <span className="font-medium">{repository.language || 'Multiple'}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-600">Stars:</span>
                <span className="font-medium">{repository.stars ?? 0}</span>
              </div>
              {repository.description && (
                <p className="border-t pt-3 text-sm text-gray-600">{repository.description}</p>
              )}
              <a
                className="text-sm text-blue-700 underline"
                href={repository.github_url}
                target="_blank"
                rel="noreferrer"
              >
                View on GitHub
              </a>
            </CardContent>
          </Card>

          {/* Analysis Status */}
          <Card>
            <CardHeader>
              <CardTitle>Analysis Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysisError ? (
                <p className="text-sm text-red-700" role="alert">
                  {analysisError instanceof Error
                    ? analysisError.message
                    : 'Unable to load analysis information.'}
                </p>
              ) : analysis ? (
                <>
                  <div className="flex items-center gap-2">
                    <div className="h-3 w-3 bg-green-500 rounded-full"></div>
                    <span className="font-medium">Completed</span>
                  </div>
                  <div className="text-sm text-gray-600">
                    {analysis.completed_at
                      ? new Date(analysis.completed_at).toLocaleString()
                      : 'Completion time unavailable'}
                  </div>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 bg-gray-300 rounded-full"></div>
                  <span className="text-gray-600">No analysis yet</span>
                </div>
              )}
              
              {job && (job.status === 'running' || job.status === 'queued') && (
                <div className="mt-4">
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>{job.current_stage || `Analysis ${job.status}...`}</span>
                  </div>
                  {job.progress !== null && job.progress !== undefined && (
                    <div className="mt-2">
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-blue-500 transition-all"
                          style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }}
                        />
                      </div>
                      <div className="mt-1 text-right text-xs text-gray-600">{job.progress}%</div>
                    </div>
                  )}
                </div>
              )}
              {job?.status === 'failed' && (
                <p className="text-sm text-red-700" role="status">Analysis failed. You can retry it below.</p>
              )}
              {jobError && (
                <p className="text-sm text-amber-700" role="status">Analysis status is unavailable.</p>
              )}
            </CardContent>
          </Card>

          {/* Statistics */}
          <Card>
            <CardHeader>
              <CardTitle>Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {analysis ? (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Files</span>
                    <span className="font-medium">{analysis.total_files?.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Symbols</span>
                    <span className="font-medium">{analysis.total_symbols ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Imports</span>
                    <span className="font-medium">{analysis.total_imports ?? 0}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-600">Calls</span>
                    <span className="font-medium">{analysis.total_calls ?? 0}</span>
                  </div>
                </>
              ) : (
                <div className="text-sm text-gray-500">No statistics available</div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Features */}
        {analysis && (
          <div className="mt-8">
            <h2 className="text-2xl font-bold mb-4">Explore</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <Link href={`/repositories/${id}/workspace`}>
                <Card className="cursor-pointer hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <FileCode className="h-8 w-8 text-blue-600 mb-2" />
                    <CardTitle>Full Workspace</CardTitle>
                    <CardDescription>
                      Files, symbols, graph, and AI investigation
                    </CardDescription>
                  </CardHeader>
                </Card>
              </Link>

              <Card className="cursor-pointer hover:shadow-lg transition-shadow opacity-60">
                <CardHeader>
                  <Code2 className="h-8 w-8 text-purple-600 mb-2" />
                  <CardTitle>Symbols</CardTitle>
                  <CardDescription>
                    Browse functions, classes, and APIs
                  </CardDescription>
                </CardHeader>
              </Card>

              <Card className="cursor-pointer hover:shadow-lg transition-shadow opacity-60">
                <CardHeader>
                  <Box className="h-8 w-8 text-green-600 mb-2" />
                  <CardTitle>Dependencies</CardTitle>
                  <CardDescription>
                    Explore dependency graph and relationships
                  </CardDescription>
                </CardHeader>
              </Card>

              <Card className="cursor-pointer hover:shadow-lg transition-shadow opacity-60">
                <CardHeader>
                  <Workflow className="h-8 w-8 text-orange-600 mb-2" />
                  <CardTitle>Workflows</CardTitle>
                  <CardDescription>
                    Visualize execution flows and data paths
                  </CardDescription>
                </CardHeader>
              </Card>

              <Card className="cursor-pointer hover:shadow-lg transition-shadow opacity-60">
                <CardHeader>
                  <GitCommit className="h-8 w-8 text-red-600 mb-2" />
                  <CardTitle>History</CardTitle>
                  <CardDescription>
                    Browse commits and file changes
                  </CardDescription>
                </CardHeader>
              </Card>
            </div>
          </div>
        )}

        {!analysis && (
          <div className="mt-8 text-center">
            <p className="text-gray-600 mb-4">This repository hasn't been analyzed yet.</p>
            <Button
              size="lg"
              onClick={handleStartAnalysis}
              disabled={startAnalysis.isPending || job?.status === 'queued' || job?.status === 'running'}
            >
              {startAnalysis.isPending ? 'Starting Analysis...' : 'Start Analysis'}
            </Button>
            {startError && <p className="mt-3 text-sm text-red-700" role="alert">{startError}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
