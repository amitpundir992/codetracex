'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ExampleChip } from '@/components/ui/example-chip';
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
      {/* Hero Section with Background Glow */}
      <div className="relative text-center space-y-4 pt-12">
        {/* Radial glow effect */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-gradient-to-b from-indigo-50/50 via-transparent to-transparent dark:from-indigo-950/20" />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-indigo-500/5 dark:bg-indigo-500/10 rounded-full blur-3xl" />
        </div>
        
        {/* Logo with enhanced shadow */}
        <div className="flex justify-center animate-in fade-in slide-in-from-top-4 duration-700">
          <div className="p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-lg shadow-indigo-500/20">
            <GitBranch className="w-10 h-10 text-white" />
          </div>
        </div>
        
        {/* Title */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 animate-in fade-in slide-in-from-top-6 duration-700 delay-75">
          CodeTraceX
        </h1>
        
        {/* Tagline */}
        <p className="text-base sm:text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto px-4 animate-in fade-in slide-in-from-top-8 duration-700 delay-150">
          Analyze any GitHub repository with AI-powered intelligence
        </p>
      </div>

      {/* Search Card */}
      <Card className="max-w-5xl mx-auto px-4">
        <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xl shadow-indigo-500/5 transition-shadow duration-200 hover:shadow-2xl hover:shadow-indigo-500/10 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-300">
          <CardHeader className="p-6 sm:p-8 pb-4">
            <CardTitle className="flex items-center gap-2 text-xl font-semibold text-slate-900 dark:text-slate-100">
              <Search className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              Repository Analysis
            </CardTitle>
            <CardDescription className="text-sm text-slate-500 dark:text-slate-400 mt-1.5">
              Enter a GitHub repository URL to start analyzing
            </CardDescription>
          </CardHeader>
          
          <CardContent className="p-6 sm:p-8 pt-0 space-y-4">
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Input Row */}
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="relative flex-1">
                  <GitBranch className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 dark:text-slate-500 pointer-events-none" />
                  <Input
                    type="text"
                    placeholder="https://github.com/owner/repository"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    disabled={loading}
                    className="h-12 pl-10 pr-4 rounded-xl border-slate-200 dark:border-slate-700 focus-visible:ring-2 focus-visible:ring-indigo-500/40 focus-visible:border-indigo-500 transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed text-sm"
                  />
                </div>
                <Button 
                  type="submit" 
                  disabled={loading || !url.trim()}
                  size="lg"
                  className="h-12 px-6 sm:px-8 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-xl shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-all duration-150 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0 text-sm"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Search className="mr-2 h-4 w-4" />
                      Analyze
                    </>
                  )}
                </Button>
              </div>

              {/* Loading Stage Indicator */}
              {loadingStage && (
                <div className="flex items-center justify-center gap-2.5 p-4 bg-indigo-50 dark:bg-indigo-950/50 border border-indigo-200 dark:border-indigo-800 rounded-xl animate-in fade-in duration-300">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-600 dark:text-indigo-400" />
                  <p className="text-sm font-medium text-indigo-900 dark:text-indigo-100">
                    {loadingStage}
                  </p>
                </div>
              )}

              {/* Example Chips */}
              {!loading && !error && (
                <div className="flex flex-wrap items-center gap-2 pt-2 animate-in fade-in duration-500 delay-100">
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                    Try examples:
                  </span>
                  {exampleRepos.map((repo) => (
                    <ExampleChip
                      key={repo}
                      label={repo}
                      onClick={() => fillExample(repo)}
                    />
                  ))}
                </div>
              )}
            </form>
          </CardContent>
        </div>
      </Card>

      {/* Error Display */}
      {error && (
        <Card className="max-w-5xl mx-auto px-4 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className="bg-red-50 dark:bg-red-950/50 rounded-2xl border border-red-200 dark:border-red-800">
            <CardContent className="p-6 sm:p-8">
              <div className="flex items-start gap-4">
                <div className="p-2.5 bg-red-100 dark:bg-red-900/50 rounded-lg flex-shrink-0">
                  <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-base text-red-900 dark:text-red-100 mb-1">
                    Analysis Failed
                  </h3>
                  <p className="text-sm text-red-700 dark:text-red-300 break-words">
                    {error}
                  </p>
                </div>
              </div>
            </CardContent>
          </div>
        </Card>
      )}
    </div>
  );
};

export default RepositoryInput;
