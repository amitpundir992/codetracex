'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { GitBranch, Loader2, AlertCircle, Search, Github } from 'lucide-react';

interface RepositoryInputProps {
  onSubmit: (url: string) => void;
  loading: boolean;
  loadingStage: string;
  error: string | null;
}

export default function RepositoryInput({ onSubmit, loading, loadingStage, error }: RepositoryInputProps) {
  const [url, setUrl] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim());
  };

  const exampleRepos = [
    'facebook/react',
    'microsoft/vscode',
    'vercel/next.js',
  ];

  const fillExample = (repo: string) => {
    setUrl(`https://github.com/${repo}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-4">
        <div className="flex justify-center">
          <div className="p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-lg">
            <GitBranch className="w-10 h-10 text-white" />
          </div>
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600">
          CodeTraceX
        </h1>
        <p className="text-lg sm:text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          Analyze any GitHub repository with AI-powered intelligence
        </p>
      </div>

      {/* Input Card */}
      <Card className="border-2 border-slate-200 dark:border-slate-800 shadow-lg">
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2">
            <Search className="w-5 h-5" />
            Repository Analysis
          </CardTitle>
          <CardDescription>
            Enter a GitHub repository URL to start analyzing
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Github className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  type="text"
                  placeholder="https://github.com/owner/repository"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={loading}
                  className="pl-10 h-12 text-base"
                />
              </div>
              <Button 
                type="submit" 
                disabled={loading || !url.trim()}
                size="lg"
                className="h-12 px-8 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Search className="mr-2 h-5 w-5" />
                    Analyze
                  </>
                )}
              </Button>
            </div>

            {/* Loading Stage Indicator */}
            {loadingStage && (
              <div className="flex items-center justify-center gap-2 p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
                <Loader2 className="w-4 h-4 animate-spin text-blue-600 dark:text-blue-400" />
                <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                  {loadingStage}
                </p>
              </div>
            )}

            {/* Example Repositories */}
            {!loading && !error && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-slate-500">Try:</span>
                {exampleRepos.map((repo) => (
                  <button
                    key={repo}
                    type="button"
                    onClick={() => fillExample(repo)}
                    className="text-sm px-3 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-full transition-colors"
                  >
                    {repo}
                  </button>
                ))}
              </div>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Card className="border-2 border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-red-100 dark:bg-red-900 rounded-lg">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-red-900 dark:text-red-100 mb-1">
                  Analysis Failed
                </h3>
                <p className="text-sm text-red-700 dark:text-red-300">
                  {error}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
