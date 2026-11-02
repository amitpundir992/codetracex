'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  FileCode, HardDrive, Layers, GitBranch, Code2, 
  Package, Zap, TrendingUp 
} from 'lucide-react';

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

export default function AnalysisSummary({
  repository,
  status,
  totalFiles,
  totalSize,
  languages,
  repositoryId,
  analysisSummary,
}: AnalysisSummaryProps) {
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
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

  return (
    <div className="space-y-6">
      {/* Repository Header */}
      <Card className="border-2 border-slate-200 dark:border-slate-800">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <CardTitle className="text-2xl sm:text-3xl flex items-center gap-2">
                <GitBranch className="w-6 h-6 text-blue-600" />
                {repository}
              </CardTitle>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={status === 'completed' ? 'default' : 'secondary'} className="font-normal">
                  {status}
                </Badge>
                {repositoryId && (
                  <span className="text-xs text-slate-500 font-mono">
                    ID: {repositoryId.substring(0, 8)}...
                  </span>
                )}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Key Metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-950 dark:to-blue-900 rounded-xl">
              <div className="flex items-center gap-2 mb-2">
                <FileCode className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                <span className="text-xs font-medium text-blue-900 dark:text-blue-100 uppercase tracking-wide">
                  Files
                </span>
              </div>
              <p className="text-3xl font-bold text-blue-900 dark:text-blue-100">
                {totalFiles.toLocaleString()}
              </p>
            </div>

            <div className="p-4 bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-950 dark:to-purple-900 rounded-xl">
              <div className="flex items-center gap-2 mb-2">
                <HardDrive className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                <span className="text-xs font-medium text-purple-900 dark:text-purple-100 uppercase tracking-wide">
                  Size
                </span>
              </div>
              <p className="text-3xl font-bold text-purple-900 dark:text-purple-100">
                {formatBytes(totalSize)}
              </p>
            </div>

            <div className="p-4 bg-gradient-to-br from-green-50 to-green-100 dark:from-green-950 dark:to-green-900 rounded-xl">
              <div className="flex items-center gap-2 mb-2">
                <Layers className="w-5 h-5 text-green-600 dark:text-green-400" />
                <span className="text-xs font-medium text-green-900 dark:text-green-100 uppercase tracking-wide">
                  Languages
                </span>
              </div>
              <p className="text-3xl font-bold text-green-900 dark:text-green-100">
                {Object.keys(languages).length}
              </p>
            </div>

            {analysisSummary && (
              <div className="p-4 bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-950 dark:to-orange-900 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Code2 className="w-5 h-5 text-orange-600 dark:text-orange-400" />
                  <span className="text-xs font-medium text-orange-900 dark:text-orange-100 uppercase tracking-wide">
                    Symbols
                  </span>
                </div>
                <p className="text-3xl font-bold text-orange-900 dark:text-orange-100">
                  {analysisSummary.total_symbols.toLocaleString()}
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Languages Bar Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Language Distribution</CardTitle>
          <CardDescription>Primary languages detected in this repository</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {sortedLanguages.map(([language, count]) => {
              const percentage = (count / totalFiles) * 100;
              return (
                <div key={language} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${getLanguageColor(language)}`} />
                      <span className="font-medium">{language}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-slate-500">{count} files</span>
                      <span className="font-semibold min-w-[3rem] text-right">
                        {percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${getLanguageColor(language)} transition-all duration-500 ease-out`}
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
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Code Analysis
            </CardTitle>
            <CardDescription>
              Deep structural analysis of your codebase
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="p-4 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2 mb-1">
                  <Package className="w-4 h-4 text-slate-500" />
                  <span className="text-xs font-medium text-slate-500">Imports</span>
                </div>
                <p className="text-2xl font-bold">{analysisSummary.total_imports.toLocaleString()}</p>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-4 h-4 text-slate-500" />
                  <span className="text-xs font-medium text-slate-500">Function Calls</span>
                </div>
                <p className="text-2xl font-bold">{analysisSummary.total_calls.toLocaleString()}</p>
              </div>

              <div className="p-4 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2 mb-1">
                  <FileCode className="w-4 h-4 text-slate-500" />
                  <span className="text-xs font-medium text-slate-500">Analyzed Files</span>
                </div>
                <p className="text-2xl font-bold">{analysisSummary.analyzed_files}</p>
              </div>
            </div>

            {/* Symbol Types */}
            {Object.keys(analysisSummary.symbols_by_type).length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-semibold mb-3 text-slate-700 dark:text-slate-300">
                  Symbol Distribution
                </h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(analysisSummary.symbols_by_type)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => (
                      <div
                        key={type}
                        className="px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg"
                      >
                        <span className="text-xs text-slate-500 capitalize">{type}</span>
                        <span className="ml-2 font-semibold">{count}</span>
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
}
