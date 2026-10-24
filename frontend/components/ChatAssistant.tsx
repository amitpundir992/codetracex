'use client';

import { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Loader2, Lightbulb, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { askRepositoryQuestion, APIError } from '@/lib/api';
import { GroundedAnswer } from '@/types/llm';

interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  answer?: GroundedAnswer;
  loading?: boolean;
  error?: string;
}

interface ChatAssistantProps {
  repositoryId: string;
  repositoryName?: string;
}

const SUGGESTED_QUESTIONS = [
  "What does this project do?",
  "What's the main workflow of this application?",
  "What technologies and frameworks are used?",
  "How is the project structured?",
  "What are the main components or modules?",
  "How does authentication work?",
];

export default function ChatAssistant({ repositoryId, repositoryName }: ChatAssistantProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Log to console for debugging
  useEffect(() => {
    console.log('ChatAssistant mounted!', { repositoryId, repositoryName });
  }, [repositoryId, repositoryName]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleAskQuestion = async (question: string) => {
    if (!question.trim() || isLoading) return;

    const userMessageId = Date.now().toString();
    const assistantMessageId = (Date.now() + 1).toString();

    // Add user message
    const userMessage: Message = {
      id: userMessageId,
      type: 'user',
      content: question,
    };

    // Add loading assistant message
    const assistantMessage: Message = {
      id: assistantMessageId,
      type: 'assistant',
      content: '',
      loading: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await askRepositoryQuestion(repositoryId, {
        question,
        top_k: 10,
        semantic_weight: 0.6,
        keyword_weight: 0.4,
      });

      // Update assistant message with response
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: response.answer.answer,
                answer: response.answer,
                loading: false,
              }
            : msg
        )
      );
    } catch (err) {
      const error = err as APIError;
      let errorMessage = 'Failed to get an answer. Please try again.';
      
      if (error.statusCode === 503) {
        errorMessage = 'AI service is temporarily unavailable. Please try again later.';
      } else if (error.statusCode === 504) {
        errorMessage = 'Request timed out. Please try a simpler question.';
      } else if (error.detail) {
        errorMessage = error.detail;
      }

      // Update assistant message with error
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: '',
                loading: false,
                error: errorMessage,
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleAskQuestion(input);
  };

  const handleSuggestedQuestion = (question: string) => {
    handleAskQuestion(question);
  };

  return (
    <>
      {/* Floating Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 p-4 bg-primary text-primary-foreground rounded-full shadow-lg hover:shadow-xl transition-all hover:scale-110 z-50"
          aria-label="Open AI Assistant"
        >
          <MessageCircle className="w-6 h-6" />
        </button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 w-96 h-[600px] z-50 flex flex-col shadow-2xl rounded-lg overflow-hidden">
          <Card className="h-full flex flex-col">
            {/* Header */}
            <CardHeader className="bg-primary text-primary-foreground py-4 px-4 flex-shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MessageCircle className="w-5 h-5" />
                  <CardTitle className="text-lg">Repository Assistant</CardTitle>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsOpen(false)}
                  className="text-primary-foreground hover:bg-primary-foreground/20"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
              {repositoryName && (
                <p className="text-xs text-primary-foreground/80 mt-1">
                  {repositoryName}
                </p>
              )}
            </CardHeader>

            {/* Messages */}
            <CardContent className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50 dark:bg-slate-950">
              {messages.length === 0 && (
                <div className="space-y-4">
                  <div className="text-center text-muted-foreground text-sm py-8">
                    <Lightbulb className="w-12 h-12 mx-auto mb-4 text-primary/60" />
                    <p className="font-semibold mb-2">Ask me anything about this repository!</p>
                    <p className="text-xs">I'll analyze the code and provide grounded answers.</p>
                  </div>

                  {/* Suggested Questions */}
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground px-2">
                      Suggested questions:
                    </p>
                    {SUGGESTED_QUESTIONS.map((question, index) => (
                      <button
                        key={index}
                        onClick={() => handleSuggestedQuestion(question)}
                        disabled={isLoading}
                        className="w-full text-left text-sm p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-primary hover:bg-primary/5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg p-3 ${
                      message.type === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800'
                    }`}
                  >
                    {message.loading ? (
                      <div className="flex items-center gap-2 text-sm">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span className="text-muted-foreground">Analyzing repository...</span>
                      </div>
                    ) : message.error ? (
                      <div className="space-y-2">
                        <div className="flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 text-destructive flex-shrink-0 mt-0.5" />
                          <p className="text-sm text-destructive">{message.error}</p>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                        
                        {/* Citations */}
                        {message.answer && message.answer.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                            <p className="text-xs font-semibold text-muted-foreground mb-2">
                              Sources ({message.answer.citations.length}):
                            </p>
                            <div className="space-y-2">
                              {message.answer.citations.slice(0, 3).map((citation, idx) => (
                                <div
                                  key={idx}
                                  className="text-xs p-2 bg-slate-50 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700"
                                >
                                  <p className="font-mono text-xs text-primary truncate">
                                    {citation.file_path}:{citation.start_line}-{citation.end_line}
                                  </p>
                                  {citation.symbol_name && (
                                    <p className="text-muted-foreground mt-1">
                                      {citation.symbol_type}: {citation.symbol_name}
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Confidence Note */}
                        {message.answer && message.answer.confidence_note && (
                          <p className="text-xs text-muted-foreground italic mt-2">
                            {message.answer.confidence_note}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </CardContent>

            {/* Input */}
            <div className="p-4 border-t bg-white dark:bg-slate-900 flex-shrink-0">
              <form onSubmit={handleSubmit} className="flex gap-2">
                <Input
                  ref={inputRef}
                  type="text"
                  placeholder="Ask a question..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={isLoading}
                  className="flex-1"
                />
                <Button type="submit" disabled={isLoading || !input.trim()} size="icon">
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </form>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
