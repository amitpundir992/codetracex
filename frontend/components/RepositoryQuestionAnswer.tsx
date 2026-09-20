/**
 * Phase 12: LLM Reasoning & Grounded Explanations
 * 
 * RepositoryQuestionAnswer component provides a simple Q&A interface
 * for asking questions about a repository and receiving grounded answers
 * with citations.
 * 
 * Features:
 * - Question input
 * - Loading state
 * - Grounded answer display
 * - Citations with source references
 * - Insufficient evidence handling
 * - Error state handling
 */
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { askRepositoryQuestion } from '@/lib/api';
import { GroundedAnswer, Citation } from '@/types/llm';
import { Loader2, AlertCircle, MessageSquare, FileText, CheckCircle, AlertTriangle } from 'lucide-react';

interface RepositoryQuestionAnswerProps {
  repositoryId: string;
  analysisRunId?: string;
}

export default function RepositoryQuestionAnswer({ 
  repositoryId, 
  analysisRunId 
}: RepositoryQuestionAnswerProps) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<GroundedAnswer | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate input
    if (!question.trim()) {
      setError('Please enter a question');
      return;
    }
    
    // Clear previous state
    setError(null);
    setAnswer(null);
    setLoading(true);
    
    try {
      const result = await askRepositoryQuestion(repositoryId, {
        question: question.trim(),
        analysis_run_id: analysisRunId,
      });
      setAnswer(result.answer);
    } catch (err: any) {
      // Handle different error types
      if (err.status === 503) {
        setError('LLM service is not available. Please configure LLM_API_KEY in the backend.');
      } else if (err.status === 504) {
        setError('The request timed out. Please try a simpler question.');
      } else if (err.status === 429) {
        setError('Rate limit exceeded. Please wait a moment and try again.');
      } else {
        setError(err.detail || err.message || 'Failed to generate answer');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleExampleQuestion = (exampleQuestion: string) => {
    setQuestion(exampleQuestion);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-primary" />
          <CardTitle>Ask About This Repository</CardTitle>
        </div>
        <CardDescription>
          Ask questions about the repository structure, code implementation, or architecture.
          Answers are grounded in the analyzed code with citations.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Question Input */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="How does the authentication service work?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={loading}
              className="flex-1"
            />
            <Button type="submit" disabled={loading || !question.trim()}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Thinking...
                </>
              ) : (
                'Ask'
              )}
            </Button>
          </div>

          {/* Example Questions */}
          {!answer && !loading && (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Example questions:</p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handleExampleQuestion('What is the main entry point of this application?')}
                  disabled={loading}
                >
                  Main entry point?
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handleExampleQuestion('How is error handling implemented?')}
                  disabled={loading}
                >
                  Error handling?
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => handleExampleQuestion('What databases or data stores are used?')}
                  disabled={loading}
                >
                  Data stores?
                </Button>
              </div>
            </div>
          )}
        </form>

        {/* Error State */}
        {error && (
          <div className="flex items-start gap-2 p-4 bg-destructive/10 text-destructive rounded-lg">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-medium">Error</p>
              <p className="text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Answer Display */}
        {answer && (
          <div className="space-y-4">
            {/* Evidence Sufficiency Indicator */}
            <div className={`flex items-center gap-2 p-3 rounded-lg ${
              answer.is_sufficient_evidence 
                ? 'bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200' 
                : 'bg-yellow-50 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200'
            }`}>
              {answer.is_sufficient_evidence ? (
                <CheckCircle className="w-5 h-5 flex-shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 flex-shrink-0" />
              )}
              <div className="flex-1">
                <p className="font-medium text-sm">
                  {answer.is_sufficient_evidence 
                    ? `Answer based on ${answer.evidence_count} code evidence items` 
                    : 'Limited evidence available'}
                </p>
                {answer.confidence_note && (
                  <p className="text-xs mt-1">{answer.confidence_note}</p>
                )}
              </div>
            </div>

            {/* Question */}
            <div>
              <h3 className="font-medium text-sm text-muted-foreground mb-2">Question</h3>
              <p className="text-base">{answer.question}</p>
            </div>

            {/* Answer */}
            <div>
              <h3 className="font-medium text-sm text-muted-foreground mb-2">Answer</h3>
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <p className="whitespace-pre-wrap">{answer.answer}</p>
              </div>
            </div>

            {/* Citations */}
            {answer.citations && answer.citations.length > 0 && (
              <div>
                <h3 className="font-medium text-sm text-muted-foreground mb-3">
                  Citations ({answer.citations.length})
                </h3>
                <div className="space-y-3">
                  {answer.citations.map((citation: Citation, idx: number) => (
                    <Card key={citation.evidence_id}>
                      <CardContent className="p-4">
                        <div className="space-y-2">
                          {/* Source Info */}
                          <div className="flex items-start gap-2">
                            <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <p className="font-mono text-sm font-medium truncate">
                                {citation.file_path}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                Lines {citation.start_line}-{citation.end_line}
                                {citation.symbol_name && (
                                  <> · <span className="font-medium">{citation.symbol_name}</span></>
                                )}
                                {citation.symbol_type && (
                                  <> ({citation.symbol_type})</>
                                )}
                              </p>
                            </div>
                          </div>

                          {/* Excerpt */}
                          {citation.excerpt && (
                            <div className="mt-2">
                              <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
                                <code>{citation.excerpt}</code>
                              </pre>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Ask Another Question */}
            <div className="pt-4 border-t">
              <Button
                variant="outline"
                onClick={() => {
                  setAnswer(null);
                  setQuestion('');
                }}
                className="w-full"
              >
                Ask Another Question
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
