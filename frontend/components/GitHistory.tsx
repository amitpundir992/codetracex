'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  getRepositoryCommits,
  getCommitDetails,
  getFileHistory,
  getFileCoChanges,
  APIError
} from '@/lib/api';
import {
  CommitSummary,
  CommitDetail,
  CommitFileChange,
  FileHistoryEntry,
  CoChangeFile
} from '@/types/repository';
import { Loader2, AlertCircle, GitCommit, FileCode, Clock, User, Hash, ChevronLeft, ChevronRight } from 'lucide-react';

interface GitHistoryProps {
  repositoryId: string;
}

export default function GitHistory({ repositoryId }: GitHistoryProps) {
  // Commit list state
  const [commits, setCommits] = useState<CommitSummary[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [totalCommits, setTotalCommits] = useState(0);
  const [loadingCommits, setLoadingCommits] = useState(false);
  const [commitsError, setCommitsError] = useState<string | null>(null);

  // Selected commit details state
  const [selectedCommit, setSelectedCommit] = useState<CommitDetail | null>(null);
  const [loadingCommitDetails, setLoadingCommitDetails] = useState(false);
  const [commitDetailsError, setCommitDetailsError] = useState<string | null>(null);

  // File history state
  const [fileHistory, setFileHistory] = useState<FileHistoryEntry[] | null>(null);
  const [fileHistoryPath, setFileHistoryPath] = useState<string | null>(null);
  const [loadingFileHistory, setLoadingFileHistory] = useState(false);
  const [fileHistoryError, setFileHistoryError] = useState<string | null>(null);

  // Co-changes state
  const [coChanges, setCoChanges] = useState<CoChangeFile[] | null>(null);
  const [coChangesPath, setCoChangesPath] = useState<string | null>(null);
  const [loadingCoChanges, setLoadingCoChanges] = useState(false);
  const [coChangesError, setCoChangesError] = useState<string | null>(null);

  const loadCommits = async (page: number = 1) => {
    setLoadingCommits(true);
    setCommitsError(null);

    try {
      const response = await getRepositoryCommits(repositoryId, page, 20);
      setCommits(response.commits);
      setCurrentPage(response.page);
      setTotalPages(response.total_pages);
      setTotalCommits(response.total);
    } catch (err) {
      if (err instanceof APIError) {
        setCommitsError(err.detail || err.message);
      } else {
        setCommitsError('Failed to load commits');
      }
    } finally {
      setLoadingCommits(false);
    }
  };

  const loadCommitDetails = async (commitId: string) => {
    setLoadingCommitDetails(true);
    setCommitDetailsError(null);
    setFileHistory(null);
    setCoChanges(null);

    try {
      const details = await getCommitDetails(repositoryId, commitId);
      setSelectedCommit(details);
    } catch (err) {
      if (err instanceof APIError) {
        setCommitDetailsError(err.detail || err.message);
      } else {
        setCommitDetailsError('Failed to load commit details');
      }
    } finally {
      setLoadingCommitDetails(false);
    }
  };

  const loadFileHistory = async (fileId: string, filePath: string) => {
    setLoadingFileHistory(true);
    setFileHistoryError(null);

    try {
      const response = await getFileHistory(repositoryId, fileId, 50);
      setFileHistory(response.history);
      setFileHistoryPath(filePath);
    } catch (err) {
      if (err instanceof APIError) {
        setFileHistoryError(err.detail || err.message);
      } else {
        setFileHistoryError('Failed to load file history');
      }
    } finally {
      setLoadingFileHistory(false);
    }
  };

  const loadCoChanges = async (fileId: string, filePath: string) => {
    setLoadingCoChanges(true);
    setCoChangesError(null);

    try {
      const response = await getFileCoChanges(repositoryId, fileId, 2, 20);
      setCoChanges(response.co_changes);
      setCoChangesPath(filePath);
    } catch (err) {
      if (err instanceof APIError) {
        setCoChangesError(err.detail || err.message);
      } else {
        setCoChangesError('Failed to load co-change data');
      }
    } finally {
      setLoadingCoChanges(false);
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getChangeTypeBadge = (changeType: string) => {
    const badges = {
      added: 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200',
      modified: 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200',
      deleted: 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200',
      renamed: 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200'
    };

    const labels = {
      added: 'A',
      modified: 'M',
      deleted: 'D',
      renamed: 'R'
    };

    return (
      <span className={`text-xs px-2 py-0.5 rounded font-semibold ${badges[changeType as keyof typeof badges] || ''}`}>
        {labels[changeType as keyof typeof labels] || changeType}
      </span>
    );
  };

  const renderCommitList = () => (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitCommit className="h-5 w-5" />
          Git History
        </CardTitle>
        <CardDescription>
          Recent commits for this repository
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button 
          onClick={() => loadCommits(1)} 
          disabled={loadingCommits}
          className="w-full"
        >
          {loadingCommits ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading commits...
            </>
          ) : (
            <>
              <GitCommit className="mr-2 h-4 w-4" />
              Load Git History
            </>
          )}
        </Button>

        {commitsError && (
          <div className="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-950 rounded">
            <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-600 mb-1">Error</h3>
              <p className="text-sm text-red-700 dark:text-red-300">{commitsError}</p>
            </div>
          </div>
        )}

        {commits.length === 0 && !loadingCommits && !commitsError && totalCommits === 0 && currentPage > 0 && (
          <div className="text-center py-8 text-muted-foreground">
            <GitCommit className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>No Git history is available for this repository.</p>
          </div>
        )}

        {commits.length > 0 && (
          <>
            <div className="space-y-2">
              {commits.map((commit) => (
                <div
                  key={commit.id}
                  onClick={() => loadCommitDetails(commit.id)}
                  className={`p-3 rounded cursor-pointer transition-colors border ${
                    selectedCommit?.id === commit.id
                      ? 'bg-primary/10 border-primary'
                      : 'bg-slate-50 dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 border-transparent'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold mb-1 truncate">
                        {commit.commit_message.split('\n')[0]}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                        <span className="flex items-center gap-1">
                          <Hash className="h-3 w-3" />
                          <span className="font-mono">{commit.commit_hash.substring(0, 7)}</span>
                        </span>
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {commit.author_name}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(commit.committed_at)}
                        </span>
                        <span className="flex items-center gap-1">
                          <FileCode className="h-3 w-3" />
                          {commit.file_change_count} file{commit.file_change_count !== 1 ? 's' : ''}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  Page {currentPage} of {totalPages} ({totalCommits} total commits)
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => loadCommits(currentPage - 1)}
                    disabled={currentPage === 1 || loadingCommits}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => loadCommits(currentPage + 1)}
                    disabled={currentPage === totalPages || loadingCommits}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );

  const renderCommitDetails = () => {
    if (!selectedCommit && !loadingCommitDetails) return null;

    return (
      <Card>
        <CardHeader>
          <CardTitle>Commit Details</CardTitle>
          <CardDescription>
            Changes made in this commit
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingCommitDetails && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          )}

          {commitDetailsError && (
            <div className="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-950 rounded">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div>
                <h3 className="font-semibold text-red-600 mb-1">Error</h3>
                <p className="text-sm text-red-700 dark:text-red-300">{commitDetailsError}</p>
              </div>
            </div>
          )}

          {selectedCommit && !loadingCommitDetails && (
            <div className="space-y-4">
              {/* Commit Info */}
              <div className="space-y-3 pb-4 border-b">
                <h3 className="text-lg font-semibold">
                  {selectedCommit.commit_message.split('\n')[0]}
                </h3>
                {selectedCommit.commit_message.split('\n').length > 1 && (
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {selectedCommit.commit_message.split('\n').slice(1).join('\n').trim()}
                  </p>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">SHA:</span>
                    <span className="ml-2 font-mono">{selectedCommit.commit_hash}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Author:</span>
                    <span className="ml-2">{selectedCommit.author_name}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Email:</span>
                    <span className="ml-2 font-mono text-xs">{selectedCommit.author_email}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Date:</span>
                    <span className="ml-2">{formatDate(selectedCommit.committed_at)}</span>
                  </div>
                </div>

                {selectedCommit.parent_hashes.length > 0 && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">
                      Parent{selectedCommit.parent_hashes.length !== 1 ? 's' : ''}:
                    </span>
                    <div className="ml-2 space-y-1 mt-1">
                      {selectedCommit.parent_hashes.map((hash, idx) => (
                        <div key={idx} className="font-mono text-xs">{hash}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Changed Files */}
              <div>
                <h4 className="text-sm font-semibold mb-3">
                  Changed Files ({selectedCommit.changes.length})
                </h4>
                {selectedCommit.changes.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic">No file changes recorded</p>
                ) : (
                  <div className="space-y-2">
                    {selectedCommit.changes.map((change) => (
                      <div
                        key={change.id}
                        className="p-3 bg-slate-50 dark:bg-slate-900 rounded"
                      >
                        <div className="flex items-start gap-2 mb-2">
                          {getChangeTypeBadge(change.change_type)}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-mono break-all">
                              {change.change_type === 'renamed' && change.old_path ? (
                                <>
                                  <span className="text-red-600 dark:text-red-400">{change.old_path}</span>
                                  {' → '}
                                  <span className="text-green-600 dark:text-green-400">{change.new_path || change.path}</span>
                                </>
                              ) : (
                                change.path
                              )}
                            </p>
                            <div className="text-xs text-muted-foreground mt-1">
                              <span className="text-green-600 dark:text-green-400">+{change.additions}</span>
                              {' / '}
                              <span className="text-red-600 dark:text-red-400">-{change.deletions}</span>
                            </div>
                          </div>
                          {change.file_id && (
                            <div className="flex gap-1">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => loadFileHistory(change.file_id!, change.path)}
                              >
                                History
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => loadCoChanges(change.file_id!, change.path)}
                              >
                                Co-changes
                              </Button>
                            </div>
                          )}
                        </div>
                        {!change.file_id && (
                          <p className="text-xs text-muted-foreground italic mt-2">
                            Historical file (not in current analysis)
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderFileHistory = () => {
    if (!fileHistory && !loadingFileHistory) return null;

    return (
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>File History</CardTitle>
              <CardDescription className="font-mono text-xs mt-1">
                {fileHistoryPath}
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setFileHistory(null);
                setFileHistoryPath(null);
              }}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loadingFileHistory && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          )}

          {fileHistoryError && (
            <div className="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-950 rounded">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div>
                <h3 className="font-semibold text-red-600 mb-1">Error</h3>
                <p className="text-sm text-red-700 dark:text-red-300">{fileHistoryError}</p>
              </div>
            </div>
          )}

          {fileHistory && fileHistory.length === 0 && (
            <p className="text-sm text-muted-foreground italic">No history found for this file</p>
          )}

          {fileHistory && fileHistory.length > 0 && (
            <div className="space-y-3">
              {fileHistory.map((entry, idx) => (
                <div key={idx} className="p-3 bg-slate-50 dark:bg-slate-900 rounded">
                  <div className="flex items-start gap-2 mb-2">
                    {getChangeTypeBadge(entry.change_type)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold mb-1 truncate">
                        {entry.commit_message.split('\n')[0]}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                        <span className="flex items-center gap-1">
                          <Hash className="h-3 w-3" />
                          <span className="font-mono">{entry.commit_hash.substring(0, 7)}</span>
                        </span>
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {entry.author_name}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(entry.committed_at)}
                        </span>
                        <span>
                          <span className="text-green-600 dark:text-green-400">+{entry.additions}</span>
                          {' / '}
                          <span className="text-red-600 dark:text-red-400">-{entry.deletions}</span>
                        </span>
                      </div>
                      {entry.change_type === 'renamed' && entry.old_path && (
                        <p className="text-xs text-muted-foreground mt-1 font-mono">
                          Renamed from: {entry.old_path}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderCoChanges = () => {
    if (!coChanges && !loadingCoChanges) return null;

    return (
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>Files Frequently Changed Together</CardTitle>
              <CardDescription className="font-mono text-xs mt-1">
                {coChangesPath}
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setCoChanges(null);
                setCoChangesPath(null);
              }}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loadingCoChanges && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          )}

          {coChangesError && (
            <div className="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-950 rounded">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div>
                <h3 className="font-semibold text-red-600 mb-1">Error</h3>
                <p className="text-sm text-red-700 dark:text-red-300">{coChangesError}</p>
              </div>
            </div>
          )}

          {coChanges && coChanges.length === 0 && (
            <p className="text-sm text-muted-foreground italic">
              No files frequently changed together with this file
            </p>
          )}

          {coChanges && coChanges.length > 0 && (
            <div className="space-y-2">
              {coChanges.map((coChange) => (
                <div
                  key={coChange.file_id}
                  className="p-3 bg-slate-50 dark:bg-slate-900 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-mono flex-1 min-w-0 truncate">
                      {coChange.file_path}
                    </p>
                    <span className="text-xs px-2 py-1 bg-primary/10 text-primary rounded font-semibold whitespace-nowrap">
                      {coChange.shared_commits} shared commit{coChange.shared_commits !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6">
      {renderCommitList()}
      {renderCommitDetails()}
      {renderFileHistory()}
      {renderCoChanges()}
    </div>
  );
}
