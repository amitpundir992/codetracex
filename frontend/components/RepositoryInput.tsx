'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { GitBranch, Loader2, AlertCircle, Search } from 'lucide-react';

interface RepositoryInputProps {
  onSubmit: (url: string) => void;
  loading: boolean;
  loadingStage: string;
  error: string | null;
}

const RepositoryInput: React.FC<RepositoryInputProps> = ({ onSubmit, loading, loadingStage, error }) => {
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
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center space-y-6 pt-8">
        <div className="flex justify-center">
          <div className="p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-lg">
            <GitBranch className="w-12 h-12 text-white" />
          </div>
        </div>
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600">
          CodeTraceX
        </h1>
        <p className="text-xl sm:text-2xl text-slate-600 dark:text-slate-400 max-w-3xl mx-auto px-4">
          Analyze any GitHub repository with AI-powered intelligence
        </p>
      </div>

      {/* Input Card */}
      <Card className="border-2 border-slate-200 dark:border-slate-800 shadow-xl max-w-5xl mx-auto">
        <CardHeader className="pb-6 pt-8">
          <CardTitle className="flex items-center gap-2 text-2xl">
            <Search className="w-6 h-6" />
            Repository Analysis
          </CardTitle>
          <CardDescription className="text-base mt-2">
            Enter a GitHub repository URL to start analyzing
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pb-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <GitBranch className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  type="text"
                  placeholder="https://github.com/owner/repository"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={loading}
                  className="pl-12 h-14 text-base"
                />
              </div>
              <Button 
                type="submit" 
                disabled={loading || !url.trim()}
                size="lg"
                className="h-14 px-10 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-base font-semibold"
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
              <div className="flex items-center justify-center gap-3 p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
                <Loader2 className="w-5 h-5 animate-spin text-blue-600 dark:text-blue-400" />
                <p className="text-base font-medium text-blue-900 dark:text-blue-100">
                  {loadingStage}
                </p>
              </div>
            )}

            {/* Example Repositories */}
            {!loading && !error && (
              <div className="flex flex-wrap items-center gap-3 pt-2">
                <span className="text-sm font-medium text-slate-600 dark:text-slate-400">Try examples:</span>
                {exampleRepos.map((repo) => (
                  <button
                    key={repo}
                    type="button"
                    onClick={() => fillExample(repo)}
                    className="text-sm px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-full transition-colors font-medium"
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
        <Card className="border-2 border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950 max-w-5xl mx-auto">
          <CardContent className="pt-8 pb-8">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-red-100 dark:bg-red-900 rounded-lg flex-shrink-0">
                <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-lg text-red-900 dark:text-red-100 mb-2">
                  Analysis Failed
                </h3>
                <p className="text-base text-red-700 dark:text-red-300">
                  {error}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default RepositoryInput;
