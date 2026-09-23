'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { analyzeRepositoryAsync, APIError } from '@/lib/api';
import { GitBranch, AlertCircle } from 'lucide-react';
import JobStatusTracker from '@/components/JobStatusTracker';

export default function AsyncRepositoryPage() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisRunId, setAnalysisRunId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Clear previous state
    setError(null);
    setAnalysisRunId(null);
    
    // Validate input
    if (!url.trim()) {
      setError('Please enter a GitHub repository URL');
      return;
    }
    
    setLoading(true);
    
    try {
      const result = await analyzeRepositoryAsync(url.trim());
      setAnalysisRunId(result.analysis_run_id);
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.detail || err.message);
      } else {
        setError('An unexpected error occurred');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleJobComplete = () => {
    // Could navigate to results page or show success message
    console.log('Analysis completed successfully');
  };

  const handleJobError = (errorMessage: string) => {
    setError(errorMessage);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto space-y-8">
          {/* Header */}
          <div className="text-center space-y-4">
            <div className="flex justify-center">
              <div className="p-3 bg-primary/10 rounded-full">
                <GitBranch className="w-12 h-12 text-primary" />
              </div>
            </div>
            <h1 className="text-4xl font-bold tracking-tight">CodeTraceX</h1>
            <p className="text-xl text-muted-foreground">
              Asynchronous Repository Analysis
            </p>
            <p className="text-sm text-muted-foreground">
              Analysis runs in the background. Track progress in real-time.
            </p>
          </div>

          {/* Input Form */}
          <Card>
            <CardHeader>
              <CardTitle>Start Analysis</CardTitle>
              <CardDescription>
                Enter a GitHub repository URL to start background analysis
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
                    {loading ? 'Starting...' : 'Analyze'}
                  </Button>
                </div>

                {error && (
                  <div className="flex items-start space-x-2 p-4 bg-destructive/10 border border-destructive/20 rounded-md">
                    <AlertCircle className="h-5 w-5 text-destructive mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium text-destructive">Error</p>
                      <p className="text-sm text-destructive/80">{error}</p>
                    </div>
                  </div>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Job Status Tracker */}
          {analysisRunId && (
            <JobStatusTracker
              analysisRunId={analysisRunId}
              onComplete={handleJobComplete}
              onError={handleJobError}
            />
          )}

          {/* Instructions */}
          {!analysisRunId && (
            <Card>
              <CardHeader>
                <CardTitle>How It Works</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-muted-foreground">
                <div>
                  <p className="font-medium text-foreground mb-2">1. Start Analysis</p>
                  <p>Enter a GitHub repository URL and click "Analyze" to queue the job.</p>
                </div>
                <div>
                  <p className="font-medium text-foreground mb-2">2. Track Progress</p>
                  <p>The job status card will show real-time progress updates as the analysis runs.</p>
                </div>
                <div>
                  <p className="font-medium text-foreground mb-2">3. View Results</p>
                  <p>Once complete, you can explore the repository insights, dependencies, and more.</p>
                </div>
                <div className="pt-4 border-t">
                  <p className="font-medium text-foreground mb-2">Benefits of Async Analysis</p>
                  <ul className="list-disc list-inside space-y-1 ml-2">
                    <li>No timeout for large repositories</li>
                    <li>Real-time progress tracking</li>
                    <li>Can cancel long-running jobs</li>
                    <li>Multiple analyses can run in parallel</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
