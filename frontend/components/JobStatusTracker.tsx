'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Loader2, CheckCircle2, XCircle, Clock, Ban } from 'lucide-react';

interface JobStatusProps {
  analysisRunId: string;
  onComplete?: () => void;
  onError?: (error: string) => void;
}

interface JobStatus {
  job_id: string | null;
  analysis_run_id: string;
  repository_id: string;
  repository_name: string;
  status: 'queued' | 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number | null;
  current_stage: string | null;
  total_files: number;
  analyzed_files: number;
  total_symbols: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export default function JobStatusTracker({ analysisRunId, onComplete, onError }: JobStatusProps) {
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const fetchJobStatus = async () => {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/jobs/${analysisRunId}`);
        
        if (!response.ok) {
          throw new Error('Failed to fetch job status');
        }

        const data = await response.json();
        setJobStatus(data);
        setLoading(false);

        // Stop polling if job is in terminal state
        if (data.status === 'completed') {
          clearInterval(intervalId);
          onComplete?.();
        } else if (data.status === 'failed') {
          clearInterval(intervalId);
          setError(data.error_message || 'Analysis failed');
          onError?.(data.error_message || 'Analysis failed');
        } else if (data.status === 'cancelled') {
          clearInterval(intervalId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch job status');
        setLoading(false);
        clearInterval(intervalId);
        onError?.(err instanceof Error ? err.message : 'Failed to fetch job status');
      }
    };

    // Initial fetch
    fetchJobStatus();

    // Poll every 2 seconds if job is not in terminal state
    intervalId = setInterval(() => {
      if (jobStatus?.status && !['completed', 'failed', 'cancelled'].includes(jobStatus.status)) {
        fetchJobStatus();
      }
    }, 2000);

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [analysisRunId, jobStatus?.status, onComplete, onError]);

  const handleCancel = async () => {
    if (!jobStatus) return;

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/jobs/${analysisRunId}/cancel`,
        {
          method: 'POST',
        }
      );

      if (!response.ok) {
        throw new Error('Failed to cancel job');
      }

      const data = await response.json();
      setJobStatus({ ...jobStatus, status: 'cancelled' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel job');
    }
  };

  if (loading && !jobStatus) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center space-x-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading job status...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && !jobStatus) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center space-x-2 text-destructive">
            <XCircle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!jobStatus) return null;

  const getStatusIcon = () => {
    switch (jobStatus.status) {
      case 'queued':
      case 'pending':
        return <Clock className="h-5 w-5 text-blue-500" />;
      case 'running':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
      case 'completed':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'cancelled':
        return <Ban className="h-5 w-5 text-gray-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (jobStatus.status) {
      case 'queued':
      case 'pending':
        return 'text-blue-600 dark:text-blue-400';
      case 'running':
        return 'text-blue-600 dark:text-blue-400';
      case 'completed':
        return 'text-green-600 dark:text-green-400';
      case 'failed':
        return 'text-red-600 dark:text-red-400';
      case 'cancelled':
        return 'text-gray-600 dark:text-gray-400';
      default:
        return '';
    }
  };

  const progress = jobStatus.progress ?? 0;
  const canCancel = ['queued', 'pending', 'running'].includes(jobStatus.status);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {getStatusIcon()}
            <span>Analysis Status</span>
          </div>
          {canCancel && (
            <Button variant="outline" size="sm" onClick={handleCancel}>
              Cancel
            </Button>
          )}
        </CardTitle>
        <CardDescription>
          Repository: {jobStatus.repository_name}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Status:</span>
          <span className={`text-sm font-semibold uppercase ${getStatusColor()}`}>
            {jobStatus.status}
          </span>
        </div>

        {/* Progress Bar */}
        {(jobStatus.status === 'running' || jobStatus.status === 'queued') && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-medium">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>
        )}

        {/* Current Stage */}
        {jobStatus.current_stage && (
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Stage:</span>
            <span className="text-sm text-muted-foreground">
              {jobStatus.current_stage}
            </span>
          </div>
        )}

        {/* Statistics */}
        {(jobStatus.total_files > 0 || jobStatus.total_symbols > 0) && (
          <div className="border-t pt-4 space-y-2">
            <div className="text-sm font-medium">Statistics</div>
            {jobStatus.total_files > 0 && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Files Scanned:</span>
                <span className="font-medium">{jobStatus.total_files}</span>
              </div>
            )}
            {jobStatus.total_symbols > 0 && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Symbols Extracted:</span>
                <span className="font-medium">{jobStatus.total_symbols}</span>
              </div>
            )}
          </div>
        )}

        {/* Error Message */}
        {jobStatus.status === 'failed' && jobStatus.error_message && (
          <div className="border-t pt-4">
            <div className="text-sm font-medium text-destructive mb-2">Error</div>
            <div className="text-sm text-muted-foreground bg-destructive/10 p-3 rounded-md">
              {jobStatus.error_message}
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div className="border-t pt-4 space-y-1 text-xs text-muted-foreground">
          {jobStatus.started_at && (
            <div>Started: {new Date(jobStatus.started_at).toLocaleString()}</div>
          )}
          {jobStatus.completed_at && (
            <div>Completed: {new Date(jobStatus.completed_at).toLocaleString()}</div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
