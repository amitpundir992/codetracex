/**
 * Unified Developer Workspace - Phase 17
 * 
 * Combined interface for repository investigation:
 * - File explorer
 * - Code viewer
 * - Symbol explorer
 * - AI investigation panel
 * - Evidence viewer
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import {
  useRepository,
  useFiles,
  useFile,
  useInvestigate,
  ApiRequestError,
  type InvestigationEvidence,
  type InvestigationResponse,
  type InvestigationRequest,
  type RepositoryFile,
} from '@/lib/hooks';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Search, FileCode, MessageSquare, GitCommit } from 'lucide-react';
import { ChangeIntelligence } from '@/components/change-intelligence';

type InvestigationClaim = NonNullable<InvestigationResponse['claims']>[number];

function normalizeEvidence(value: unknown): InvestigationEvidence[] {
  if (!Array.isArray(value)) return [];

  return value.flatMap((entry): InvestigationEvidence[] => {
    if (!entry || typeof entry !== 'object') return [];
    const item = entry as Record<string, unknown>;
    return [{
      evidence_id: typeof item.evidence_id === 'string' ? item.evidence_id : undefined,
      evidence_type: typeof item.evidence_type === 'string' ? item.evidence_type : undefined,
      retrieval_source: typeof item.retrieval_source === 'string' ? item.retrieval_source : undefined,
      content: typeof item.content === 'string' ? item.content : undefined,
      file_path: typeof item.file_path === 'string' ? item.file_path : undefined,
      start_line: typeof item.start_line === 'number' ? item.start_line : undefined,
      end_line: typeof item.end_line === 'number' ? item.end_line : undefined,
      symbol_name: typeof item.symbol_name === 'string' ? item.symbol_name : undefined,
      symbol_type: typeof item.symbol_type === 'string' ? item.symbol_type : undefined,
      retrieval_score: typeof item.retrieval_score === 'number' ? item.retrieval_score : undefined,
    }];
  });
}

function normalizeClaims(value: unknown): InvestigationClaim[] {
  if (!Array.isArray(value)) return [];

  return value.flatMap((entry): InvestigationClaim[] => {
    if (!entry || typeof entry !== 'object') return [];
    const claim = entry as Record<string, unknown>;
    if (typeof claim.claim_text !== 'string') return [];
    return [{
      claim_text: claim.claim_text,
      certainty: typeof claim.certainty === 'string' ? claim.certainty as InvestigationClaim['certainty'] : 'uncertain',
      evidence_ids: Array.isArray(claim.evidence_ids)
        ? claim.evidence_ids.filter((id): id is string => typeof id === 'string')
        : [],
      reasoning: typeof claim.reasoning === 'string' ? claim.reasoning : null,
    }];
  });
}

export default function WorkspacePage({ params }: { params: { id: string } }) {
  return <WorkspaceContent key={params.id} repositoryId={params.id} />;
}

function WorkspaceContent({ repositoryId }: { repositoryId: string }) {
  const { data: repository, isLoading: repositoryLoading, error: repositoryError } = useRepository(repositoryId);
  const { data: filesData, isLoading: filesLoading, error: filesError } = useFiles(repositoryId);
  const investigate = useInvestigate(repositoryId);

  const [selectedFile, setSelectedFile] = useState<RepositoryFile | null>(null);
  const [question, setQuestion] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [conversationContext, setConversationContext] = useState<InvestigationRequest['conversation_context']>();
  const [selectedLine, setSelectedLine] = useState<number | null>(null);
  const [rightPanelTab, setRightPanelTab] = useState<'investigation' | 'changes'>('investigation');
  const lineElements = useRef(new Map<number, HTMLDivElement>());
  const {
    data: fileContent,
    isLoading: fileLoading,
    error: fileError,
  } = useFile(repositoryId, selectedFile?.id ?? '');

  const files = filesData ?? [];
  const filteredFiles = searchQuery
    ? files.filter((file) => file.path.toLowerCase().includes(searchQuery.toLowerCase()))
    : files;

  useEffect(() => {
    if (selectedLine) lineElements.current.get(selectedLine)?.scrollIntoView({ block: 'center' });
  }, [selectedLine, fileContent?.content]);

  const handleAsk = async (nextQuestion = question) => {
    const normalizedQuestion = nextQuestion.trim();
    if (!normalizedQuestion || investigate.isPending) return;

    setQuestion(normalizedQuestion);
    try {
      const response = await investigate.mutateAsync({
        question: normalizedQuestion,
        conversation_context: conversationContext,
        max_evidence: 10,
        include_graph: true,
        include_workflow: true,
      });
      setConversationContext(response.conversation_context);
    } catch {
      // The mutation error is rendered in the investigation panel.
    }
  };

  const selectEvidence = (evidence: InvestigationEvidence) => {
    if (typeof evidence.file_path !== 'string' || !evidence.file_path) return;
    const file = files.find((item) => item.path === evidence.file_path);
    if (!file || file.is_sensitive) return;
    setSelectedFile(file);
    setSelectedLine(evidence.start_line ?? evidence.end_line ?? null);
  };

  const selectFile = (file: RepositoryFile, line?: number) => {
    if (file.is_sensitive) return;
    setSelectedFile(file);
    setSelectedLine(line ?? null);
  };

  const evidence = normalizeEvidence(investigate.data?.evidence);
  const claims = normalizeClaims(investigate.data?.claims);
  const followUps = Array.isArray(investigate.data?.follow_up_questions)
    ? investigate.data.follow_up_questions.filter(
        (item) => item && typeof item === 'object' && typeof item.question === 'string'
      )
    : [];
  const limitations = Array.isArray(investigate.data?.limitations)
    ? investigate.data.limitations.filter((item): item is string => typeof item === 'string')
    : [];

  return (
    <div className="flex h-screen min-h-0 flex-col bg-gray-50">
      <div className="flex items-center justify-between border-b bg-white px-6 py-3">
        <div>
          <h1 className="text-xl font-bold">{repository?.name || 'Repository workspace'}</h1>
          <p className="text-sm text-gray-600">
            {repositoryLoading ? 'Loading repository…' : repository?.full_name || ''}
          </p>
        </div>
        <a className="text-sm text-blue-700 underline" href={`/repositories/${encodeURIComponent(repositoryId)}`}>
          Repository dashboard
        </a>
      </div>

      {repositoryError && (
        <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-800" role="alert">
          {repositoryError instanceof ApiRequestError
            ? repositoryError.message
            : 'Unable to reach the backend. Please try again.'}
        </div>
      )}

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside className="flex w-72 shrink-0 flex-col border-r bg-white">
          <div className="border-b p-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {filesLoading && <p className="p-3 text-sm text-gray-600">Loading files…</p>}
            {filesError && (
              <p className="p-3 text-sm text-red-700" role="alert">
                {filesError instanceof ApiRequestError
                  ? filesError.message
                  : 'Unable to load repository files. Check the backend connection.'}
              </p>
            )}
            {!filesLoading && !filesError && filteredFiles.length === 0 && (
              <p className="p-3 text-sm text-gray-500">
                {searchQuery ? 'No files match this search.' : 'No files are available for this analysis.'}
              </p>
            )}
            {filteredFiles.map((file) => (
              <button
                key={file.id}
                type="button"
                aria-pressed={selectedFile?.id === file.id}
                disabled={file.is_sensitive}
                onClick={() => {
                  setSelectedFile(file);
                  setSelectedLine(null);
                }}
                className={`w-full rounded px-3 py-2 text-left text-sm transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 ${
                  selectedFile?.id === file.id ? 'bg-blue-50 text-blue-700' : ''
                }`}
                title={file.is_sensitive ? 'Sensitive file content is unavailable' : file.path}
              >
                <div className="flex items-center gap-2">
                  <FileCode className="h-4 w-4 flex-shrink-0" />
                  <span className="truncate">{file.path}</span>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {selectedFile ? (
            <div className="min-h-0 flex-1 overflow-auto bg-white p-6">
              <div className="mb-4 border-b pb-3">
                <h2 className="break-all text-lg font-semibold">{selectedFile.path}</h2>
                <div className="mt-1 flex gap-4 text-sm text-gray-600">
                  <span>Language: {selectedFile.language || 'Unknown'}</span>
                  <span>Size: {((selectedFile.size_bytes ?? 0) / 1024).toFixed(1)} KB</span>
                  {selectedFile.line_count !== null && <span>{selectedFile.line_count} lines</span>}
                </div>
              </div>

              {fileLoading && <p className="text-sm text-gray-600">Loading source…</p>}
              {fileError && (
                <p className="text-sm text-red-700" role="alert">
                  {fileError instanceof ApiRequestError
                    ? fileError.message
                    : 'Unable to load this file. Check the backend connection.'}
                </p>
              )}
              {fileContent && (
                <div className="overflow-x-auto rounded border bg-gray-50 font-mono text-xs">
                  {fileContent.content.split(/\r?\n/).map((line, index) => {
                    const lineNumber = index + 1;
                    const isCitationLine = selectedLine === lineNumber;
                    return (
                      <div
                        key={lineNumber}
                        ref={(element) => {
                          if (element) lineElements.current.set(lineNumber, element);
                          else lineElements.current.delete(lineNumber);
                        }}
                        className={`flex min-h-5 ${isCitationLine ? 'bg-yellow-100' : 'hover:bg-gray-100'}`}
                      >
                        <span className="sticky left-0 w-12 shrink-0 select-none border-r bg-gray-100 px-2 text-right text-gray-500">
                          {lineNumber}
                        </span>
                        <code className="whitespace-pre px-3">{line || ' '}</code>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-1 items-center justify-center text-gray-500">
              <div className="text-center">
                <FileCode className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                <p>Select a file to view its contents</p>
              </div>
            </div>
          )}
        </main>

        <aside className="flex w-96 shrink-0 flex-col border-l bg-white">
          <div className="border-b">
            <div className="flex">
              <button
                type="button"
                onClick={() => setRightPanelTab('investigation')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                  rightPanelTab === 'investigation'
                    ? 'border-b-2 border-blue-600 text-blue-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <MessageSquare className="h-4 w-4" />
                AI Investigation
              </button>
              <button
                type="button"
                onClick={() => setRightPanelTab('changes')}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
                  rightPanelTab === 'changes'
                    ? 'border-b-2 border-blue-600 text-blue-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <GitCommit className="h-4 w-4" />
                Change Intelligence
              </button>
            </div>
          </div>

          {rightPanelTab === 'investigation' ? (
            <>
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {investigate.isError && (
                  <p className="mb-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
                    {investigate.error instanceof ApiRequestError
                      ? investigate.error.message
                      : 'Investigation is temporarily unavailable. Check the backend connection.'}
                  </p>
                )}
                {investigate.isPending && (
                  <p className="mb-3 flex items-center gap-2 text-sm text-gray-600" role="status">
                    <Loader2 className="h-4 w-4 animate-spin" /> Investigating repository...
                  </p>
                )}

                {investigate.data ? (
                  <div className="space-y-4">
                    <Card className="p-4">
                      {investigate.data.detected_intent && (
                        <div className="mb-2 text-xs text-gray-500">
                          Intent: {investigate.data.detected_intent}
                        </div>
                      )}
                      <div className="text-sm font-medium mb-2">Answer</div>
                      <div className="text-sm text-gray-700">{investigate.data.answer}</div>
                    </Card>

                {claims.length > 0 && (
                  <Card className="p-4">
                    <div className="text-sm font-medium mb-2">Claims</div>
                    <div className="space-y-2">
                      {claims.map((claim, index) => (
                        <div key={`${claim.claim_text}-${index}`} className="text-sm">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              claim.certainty === 'confirmed' 
                                ? 'bg-green-100 text-green-700'
                                : claim.certainty === 'inferred'
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-gray-100 text-gray-700'
                            }`}>
                              {claim.certainty}
                            </span>
                          </div>
                          <div className="text-gray-700">{claim.claim_text}</div>
                          {claim.reasoning && <p className="mt-1 text-xs text-gray-500">{claim.reasoning}</p>}
                          {claim.evidence_ids?.length ? (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {claim.evidence_ids.map((evidenceId) => {
                                const citedEvidence = evidence.find((item) => item.evidence_id === evidenceId);
                                return (
                                  <button
                                    key={evidenceId}
                                    type="button"
                                    className="text-xs text-blue-700 underline disabled:text-gray-400"
                                    disabled={!citedEvidence?.file_path}
                                    onClick={() => citedEvidence && selectEvidence(citedEvidence)}
                                  >
                                    {evidenceId}
                                  </button>
                                );
                              })}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {evidence.length > 0 && (
                  <Card className="p-4">
                    <div className="text-sm font-medium mb-2">Evidence</div>
                    <div className="space-y-2">
                      {evidence.map((item, index) => {
                        const claim = claims.find((candidate) =>
                          candidate.evidence_ids?.includes(item.evidence_id || '')
                        );
                        const canNavigate = !!item.file_path && files.some((file) => file.path === item.file_path);
                        return (
                          <button
                            key={item.evidence_id || `${item.file_path || 'evidence'}-${index}`}
                            type="button"
                            disabled={!canNavigate}
                            onClick={() => selectEvidence(item)}
                            className="block w-full rounded border bg-gray-50 p-2 text-left text-xs hover:bg-gray-100 disabled:cursor-default disabled:opacity-70"
                          >
                            <span className="font-semibold text-blue-700">
                              {item.evidence_type || 'Evidence'}
                            </span>
                            {item.evidence_id && <span className="ml-2 text-gray-500">{item.evidence_id}</span>}
                            {item.file_path && <span className="mt-1 block break-all">{item.file_path}</span>}
                            {(item.start_line || item.end_line) && (
                              <span className="mt-1 block text-gray-600">
                                Lines {item.start_line ?? '?'}-{item.end_line ?? item.start_line ?? '?'}
                              </span>
                            )}
                            {(item.symbol_name || item.symbol_type) && (
                              <span className="mt-1 block text-gray-600">
                                {[item.symbol_name, item.symbol_type].filter(Boolean).join(' / ')}
                              </span>
                            )}
                            {claim?.certainty && (
                              <span className="mt-1 block text-gray-600">Claim certainty: {claim.certainty}</span>
                            )}
                            {item.retrieval_source && (
                              <span className="mt-1 block text-gray-500">Source: {item.retrieval_source}</span>
                            )}
                            {item.content && <span className="mt-2 block whitespace-pre-wrap text-gray-700">{item.content}</span>}
                          </button>
                        );
                      })}
                    </div>
                  </Card>
                )}

                {limitations.length > 0 ? (
                  <Card className="p-4">
                    <div className="mb-2 text-sm font-medium">Limitations</div>
                    <ul className="list-disc space-y-1 pl-5 text-xs text-gray-700">
                      {limitations.map((limitation, index) => (
                        <li key={`${limitation}-${index}`}>{limitation}</li>
                      ))}
                    </ul>
                  </Card>
                ) : null}

                {followUps.length > 0 && (
                  <Card className="p-4">
                    <div className="text-sm font-medium mb-2">Follow-up Questions</div>
                    <div className="space-y-2">
                      {followUps.map((followUp, index) => (
                        <button
                          key={`${followUp.question}-${index}`}
                          type="button"
                          disabled={investigate.isPending}
                          onClick={() => void handleAsk(followUp.question)}
                          className="w-full rounded border p-2 text-left text-xs hover:bg-gray-50 disabled:opacity-50"
                        >
                          {followUp.question}
                        </button>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                <MessageSquare className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                <p className="text-sm">Ask a question about this repository</p>
              </div>
            )}
          </div>
          
          <div className="border-t p-4">
            <Input
              placeholder="Ask about this repository..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void handleAsk();
                }
              }}
              className="mb-2"
            />
            <Button
              onClick={() => void handleAsk()}
              disabled={investigate.isPending || !question.trim()}
              className="w-full"
            >
              {investigate.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Investigating...
                </>
              ) : (
                'Ask'
              )}
            </Button>
          </div>
        </>
      ) : (
        <ChangeIntelligence
          repositoryId={repositoryId}
          files={files}
          onFileSelect={selectFile}
        />
      )}
    </aside>
      </div>
    </div>
  );
}
