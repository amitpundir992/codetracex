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

import { use, useState } from 'react';
import { useRepository, useFiles, useInvestigate } from '@/lib/hooks';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Loader2, Search, FileCode, MessageSquare } from 'lucide-react';

export default function WorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: repository } = useRepository(id);
  const { data: filesData } = useFiles(id);
  const investigate = useInvestigate(id);
  
  const [selectedFile, setSelectedFile] = useState<any>(null);
  const [question, setQuestion] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const files = filesData?.files || [];
  const filteredFiles = searchQuery
    ? files.filter((f: any) => 
        f.relative_path.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : files;

  const handleAsk = async () => {
    if (!question.trim()) return;
    
    await investigate.mutateAsync({
      question: question.trim(),
      max_evidence: 10,
      include_graph: true,
      include_workflow: true,
    });
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{repository?.name}</h1>
          <p className="text-sm text-gray-600">{repository?.full_name}</p>
        </div>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar - File Explorer */}
        <div className="w-80 bg-white border-r flex flex-col">
          <div className="p-4 border-b">
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
          
          <div className="flex-1 overflow-y-auto p-2">
            {filteredFiles.slice(0, 100).map((file: any) => (
              <button
                key={file.id}
                onClick={() => setSelectedFile(file)}
                className={`w-full text-left px-3 py-2 rounded text-sm hover:bg-gray-100 transition-colors ${
                  selectedFile?.id === file.id ? 'bg-blue-50 text-blue-700' : ''
                }`}
              >
                <div className="flex items-center gap-2">
                  <FileCode className="h-4 w-4 flex-shrink-0" />
                  <span className="truncate">{file.relative_path}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Center - Code Viewer / Content */}
        <div className="flex-1 flex flex-col">
          {selectedFile ? (
            <div className="flex-1 bg-white p-6 overflow-y-auto">
              <div className="mb-4">
                <h2 className="text-lg font-semibold">{selectedFile.relative_path}</h2>
                <div className="flex gap-4 text-sm text-gray-600 mt-1">
                  <span>Language: {selectedFile.language}</span>
                  <span>Size: {(selectedFile.size_bytes / 1024).toFixed(1)} KB</span>
                </div>
              </div>
              
              <Card className="p-4 bg-gray-50">
                <pre className="text-xs overflow-x-auto">
                  <code>
                    {`// File content would be displayed here
// With syntax highlighting using prism-react-renderer
// Line numbers and citation highlights

function example() {
  // File: ${selectedFile.relative_path}
  // Language: ${selectedFile.language}
  return "Code viewer implementation";
}`}
                  </code>
                </pre>
              </Card>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <FileCode className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                <p>Select a file to view its contents</p>
              </div>
            </div>
          )}
        </div>

        {/* Right Sidebar - AI Panel */}
        <div className="w-96 bg-white border-l flex flex-col">
          <div className="p-4 border-b">
            <h2 className="font-semibold flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              AI Investigation
            </h2>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4">
            {investigate.data ? (
              <div className="space-y-4">
                <Card className="p-4">
                  <div className="text-sm font-medium mb-2">Answer</div>
                  <div className="text-sm text-gray-700">{investigate.data.answer}</div>
                </Card>
                
                {investigate.data.claims && investigate.data.claims.length > 0 && (
                  <Card className="p-4">
                    <div className="text-sm font-medium mb-2">Claims</div>
                    <div className="space-y-2">
                      {investigate.data.claims.map((claim: any, idx: number) => (
                        <div key={idx} className="text-sm">
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
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
                
                {investigate.data.evidence && investigate.data.evidence.length > 0 && (
                  <Card className="p-4">
                    <div className="text-sm font-medium mb-2">Evidence</div>
                    <div className="space-y-2">
                      {investigate.data.evidence.slice(0, 5).map((evidence: any) => (
                        <div
                          key={evidence.evidence_id}
                          className="text-xs bg-gray-50 p-2 rounded cursor-pointer hover:bg-gray-100"
                          onClick={() => {
                            // Find and select the file
                            const file = files.find((f: any) => f.relative_path === evidence.file_path);
                            if (file) setSelectedFile(file);
                          }}
                        >
                          <div className="font-medium text-blue-600 mb-1">
                            {evidence.file_path}
                          </div>
                          {evidence.symbol_name && (
                            <div className="text-gray-600">
                              {evidence.symbol_name} ({evidence.symbol_type})
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
                
                {investigate.data.follow_up_questions && investigate.data.follow_up_questions.length > 0 && (
                  <Card className="p-4">
                    <div className="text-sm font-medium mb-2">Follow-up Questions</div>
                    <div className="space-y-2">
                      {investigate.data.follow_up_questions.map((fq: any, idx: number) => (
                        <button
                          key={idx}
                          onClick={() => setQuestion(fq.question)}
                          className="w-full text-left text-xs p-2 rounded hover:bg-gray-50 border"
                        >
                          {fq.question}
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
          
          {/* Question Input */}
          <div className="p-4 border-t">
            <Input
              placeholder="Ask about this repository..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAsk();
                }
              }}
              className="mb-2"
            />
            <Button
              onClick={handleAsk}
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
        </div>
      </div>
    </div>
  );
}
