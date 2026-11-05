'use client';

import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { StatCard } from '@/components/ui/stat-card';
import { StatusBadge } from '@/components/ui/status-badge';
import { Button } from '@/components/ui/button';
import { 
  FileCode, HardDrive, Layers, GitBranch, Code2, 
  Package, Zap, ExternalLink, Copy, Check
} from 'lucide-react';
import { useState } from 'react';

interface AnalysisSummaryProps {
  repository: string;
  status: string;
  totalFiles: number;
  totalSize: number;
  languages: Record<string, number>;
  repositoryId?: string;
  analysisSummary?: {
    analyzed_files: number;
    total_files: number;
    total_symbols: number;
    total_imports: number;
    total_calls: number;
    symbols_by_type: Record<string, number>;
  };
}

const AnalysisSummary: React.FC<AnalysisSummaryProps> = ({
  repository,
  status,
  totalFiles,
  totalSize,
  languages,
  repositoryId,
  analysisSummary,
}) => {
  const [copied, setCopied] = useState(false);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getLanguageColor = (language: string): string => {
    const colors: Record<string, string> = {
      'TypeScript': 'bg-blue-500',
      'JavaScript': 'bg-yellow-500',
      'Python': 'bg-green-500',
      'Java': 'bg-red-500',
      'Go': 'bg-cyan-500',
      'Rust': 'bg-orange-500',
      'Ruby': 'bg-pink-500',
      'PHP': 'bg-purple-500',
      'C++': 'bg-indigo-500',
      'C#': 'bg-violet-500',
    };
    return colors[language] || 'bg-slate-500';
  };

  const sortedLanguages = Object.entries(languages)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6);

  const githubUrl = `https://github.com/${repository}`;

  return (
    <div className="max-w-5xl mx-auto px-4 space-y-12 animate-in fade-in slide-in-from-bottom-8 duration-700">
      {/* Repository Header Card */}
      <Card className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-lg">
        <CardHeader className="p-6 sm:p-8">
          <div className="flex flex-col gap-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="p-2 bg-indigo-100 dark:bg-indigo-900/50 rounded-lg flex-shrink-0">
                  <GitBranch className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <a 
                    href={githubUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-2xl font-bold text-slate-900 dark:text-slate-100 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors inline-flex items-center gap-2 group"
                  >
                    <span className="truncate">{repository}</span>
                    <ExternalLink className="w-5 h-5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                  </a>
                </div>
              </div>
            </div>
            
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status={status as any} />
              {repositoryId && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                    {repositoryId.substring(0, 12)}...
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(repositoryId)}
                    className="h-6 w-6 p-0 hover:bg-slate-100 dark:hover:bg-slate-800"
                  >
                    {copied ? (
                      <Check className="w-3 h-3 text-green-600" />
                    ) : (
                      <Copy className="w-3 h-3 text-slate-400" />
                    )}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-6 sm:p-8 pt-0">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              icon={FileCode}
              label="Files"
              value={totalFiles}
              color="blue"
            />
            <StatCard
              icon={HardDrive}
              label="Size"
              value={formatBytes(totalSize)}
              color="purple"
              animate={false}
            />
            <StatCard
              icon={Layers}
              label="Languages"
              value={Object.keys(languages).length}
              color="green"
            />
            {analysisSummary ? (
              <StatCard
                icon={Code2}
                label="Symbols"
                value={analysisSummary.total_symbols}
                color="orange"
              />
            ) : (
              <StatCard
                icon={Code2}
                label="Symbols"
                value="—"
                color="orange"
                animate={false}
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Language Distribution Card */}
      <Card className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-lg">
        <CardHeader className="p-6 sm:p-8 pb-6">
          <CardTitle className="text-xl font-semibold">Language Distribution</CardTitle>
          <CardDescription>Primary languages detected in this repository</CardDescription>
        </CardHeader>
        <CardContent className="p-6 sm:p-8 pt-0">
          <div className="space-y-4">
            {sortedLanguages.map(([language, count]) => {
              const percentage = (count / totalFiles) * 100;
              return (
                <div key={language} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-3 h-3 rounded-full ${getLanguageColor(language)}`} />
                      <span className="font-medium text-slate-900 dark:text-slate-100">{language}</span>
                    </div>
                    <div className="flex items-center gap-3 text-slate-600 dark:text-slate-400">
                      <span className="text-xs">{count} files</span>
                      <span className="font-semibold min-w-[3rem] text-right">
                        {percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getLanguageColor(language)} transition-all duration-700 ease-out`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Code Analysis Stats */}
      {analysisSummary && (
        <Card className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-lg">
          <CardHeader className="p-6 sm:p-8 pb-6">
            <CardTitle className="flex items-center gap-2 text-xl font-semibold">
              <Code2 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              Code Analysis
            </CardTitle>
            <CardDescription>
              Deep structural analysis of your codebase
            </CardDescription>
          </CardHeader>
          <CardContent className="p-6 sm:p-8 pt-0">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <Package className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">Imports</span>
                </div>
                <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {analysisSummary.total_imports.toLocaleString()}
                </p>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">Function Calls</span>
                </div>
                <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {analysisSummary.total_calls.toLocaleString()}
                </p>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <FileCode className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">Analyzed Files</span>
                </div>
                <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {analysisSummary.analyzed_files.toLocaleString()}
                </p>
              </div>
            </div>

            {/* Symbol Types */}
            {Object.keys(analysisSummary.symbols_by_type).length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300">
                  Symbol Distribution
                </h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(analysisSummary.symbols_by_type)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => (
                      <div
                        key={type}
                        className="px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors"
                      >
                        <span className="text-xs text-slate-600 dark:text-slate-400 capitalize">{type}</span>
                        <span className="ml-2 font-semibold text-slate-900 dark:text-slate-100">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default AnalysisSummary;
