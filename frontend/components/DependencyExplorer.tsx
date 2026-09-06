'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  getSymbolCallers,
  getSymbolCallees,
  getSymbolDependencies,
  getSymbolDependents,
  getSymbolImpact,
  APIError
} from '@/lib/api';
import {
  GraphEdge,
  GraphNode,
  SymbolCallersResponse,
  SymbolCalleesResponse,
  SymbolDependenciesResponse,
  SymbolDependentsResponse,
  ImpactAnalysisResponse
} from '@/types/repository';
import { Loader2, AlertCircle, ArrowRight, ArrowLeft, Network, Target } from 'lucide-react';

interface DependencyExplorerProps {
  repositoryId: string;
  symbolId: string;
  symbolName: string;
}

export default function DependencyExplorer({ repositoryId, symbolId, symbolName }: DependencyExplorerProps) {
  const [depth, setDepth] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [callers, setCallers] = useState<SymbolCallersResponse | null>(null);
  const [callees, setCallees] = useState<SymbolCalleesResponse | null>(null);
  const [dependencies, setDependencies] = useState<SymbolDependenciesResponse | null>(null);
  const [dependents, setDependents] = useState<SymbolDependentsResponse | null>(null);
  const [impact, setImpact] = useState<ImpactAnalysisResponse | null>(null);

  const loadGraphData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [callersData, calleesData, depsData, dependentsData, impactData] = await Promise.all([
        getSymbolCallers(repositoryId, symbolId, depth),
        getSymbolCallees(repositoryId, symbolId, depth),
        getSymbolDependencies(repositoryId, symbolId, depth),
        getSymbolDependents(repositoryId, symbolId, depth),
        getSymbolImpact(repositoryId, symbolId, Math.max(depth, 3))
      ]);

      setCallers(callersData);
      setCallees(calleesData);
      setDependencies(depsData);
      setDependents(dependentsData);
      setImpact(impactData);
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.detail || err.message);
      } else {
        setError('Failed to load dependency data');
      }
    } finally {
      setLoading(false);
    }
  };

  const renderEdgeList = (edges: GraphEdge[], title: string, icon: React.ReactNode) => {
    if (edges.length === 0) {
      return (
        <div className="text-sm text-muted-foreground italic">
          No {title.toLowerCase()} found
        </div>
      );
    }

    return (
      <div className="space-y-2">
        {edges.map((edge, index) => (
          <div key={index} className="flex items-start gap-2 p-2 bg-slate-50 dark:bg-slate-900 rounded">
            <div className="mt-1">{icon}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold truncate">
                  {edge.source.name}
                </span>
                <ArrowRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                <span className="font-mono text-sm truncate">
                  {edge.target.name}
                </span>
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                <span className="px-1.5 py-0.5 bg-primary/10 text-primary rounded mr-2">
                  {edge.source.type}
                </span>
                {edge.source.file && (
                  <span className="font-mono">{edge.source.file}</span>
                )}
                {edge.line_number && (
                  <span className="ml-2">: Line {edge.line_number}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderNodeList = (nodes: GraphNode[], title: string) => {
    if (nodes.length === 0) {
      return (
        <div className="text-sm text-muted-foreground italic">
          No {title.toLowerCase()} found
        </div>
      );
    }

    return (
      <div className="space-y-2">
        {nodes.map((node, index) => (
          <div key={index} className="p-2 bg-slate-50 dark:bg-slate-900 rounded">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold">
                {node.name}
              </span>
              <span className="text-xs px-1.5 py-0.5 bg-primary/10 text-primary rounded">
                {node.type}
              </span>
            </div>
            {node.file && (
              <div className="text-xs text-muted-foreground mt-1 font-mono">
                {node.file}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Network className="h-5 w-5" />
            Dependency Explorer
          </CardTitle>
          <CardDescription>
            Analyze dependencies and impact for <span className="font-mono font-semibold">{symbolName}</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Depth Selector */}
          <div>
            <label className="text-sm font-semibold mb-2 block">
              Traversal Depth
            </label>
            <div className="flex items-center gap-2">
              {[1, 2, 3, 4, 5].map((d) => (
                <Button
                  key={d}
                  variant={depth === d ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setDepth(d)}
                  disabled={loading}
                >
                  {d}
                </Button>
              ))}
              <span className="text-xs text-muted-foreground ml-2">
                {depth === 1 && 'Direct relationships only'}
                {depth === 2 && 'Direct + one level'}
                {depth >= 3 && `Up to ${depth} levels deep`}
              </span>
            </div>
          </div>

          {/* Load Button */}
          <Button onClick={loadGraphData} disabled={loading} className="w-full">
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading dependencies...
              </>
            ) : (
              <>
                <Network className="mr-2 h-4 w-4" />
                Load Dependency Graph
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-destructive mt-0.5" />
              <div>
                <h3 className="font-semibold text-destructive mb-1">Error</h3>
                <p className="text-sm text-muted-foreground">{error}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Callers */}
      {callers && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <ArrowLeft className="h-4 w-4" />
                Callers
              </span>
              <span className="text-sm font-normal text-muted-foreground">
                {callers.total_callers} total
              </span>
            </CardTitle>
            <CardDescription>
              Symbols that call {symbolName}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {renderEdgeList(callers.callers, 'Callers', <ArrowLeft className="h-4 w-4 text-blue-500" />)}
          </CardContent>
        </Card>
      )}

      {/* Callees */}
      {callees && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <ArrowRight className="h-4 w-4" />
                Callees
              </span>
              <span className="text-sm font-normal text-muted-foreground">
                {callees.total_callees} total
              </span>
            </CardTitle>
            <CardDescription>
              Symbols that {symbolName} calls
            </CardDescription>
          </CardHeader>
          <CardContent>
            {renderEdgeList(callees.callees, 'Callees', <ArrowRight className="h-4 w-4 text-green-500" />)}
          </CardContent>
        </Card>
      )}

      {/* Dependencies */}
      {dependencies && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Network className="h-4 w-4" />
                Dependencies
              </span>
              <span className="text-sm font-normal text-muted-foreground">
                {dependencies.total_dependencies} total
              </span>
            </CardTitle>
            <CardDescription>
              What {symbolName} depends on
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {dependencies.calls.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Function Calls</h4>
                {renderEdgeList(dependencies.calls, 'Calls', <ArrowRight className="h-4 w-4 text-purple-500" />)}
              </div>
            )}
            {dependencies.imports.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Imports</h4>
                {renderEdgeList(dependencies.imports, 'Imports', <ArrowRight className="h-4 w-4 text-orange-500" />)}
              </div>
            )}
            {dependencies.calls.length === 0 && dependencies.imports.length === 0 && (
              <div className="text-sm text-muted-foreground italic">
                No dependencies found
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Dependents */}
      {dependents && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Network className="h-4 w-4" />
                Dependents
              </span>
              <span className="text-sm font-normal text-muted-foreground">
                {dependents.total_dependents} total
              </span>
            </CardTitle>
            <CardDescription>
              What depends on {symbolName}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {dependents.callers.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Called By</h4>
                {renderEdgeList(dependents.callers, 'Callers', <ArrowLeft className="h-4 w-4 text-blue-500" />)}
              </div>
            )}
            {dependents.imported_by.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Imported By</h4>
                {renderEdgeList(dependents.imported_by, 'Imports', <ArrowLeft className="h-4 w-4 text-orange-500" />)}
              </div>
            )}
            {dependents.callers.length === 0 && dependents.imported_by.length === 0 && (
              <div className="text-sm text-muted-foreground italic">
                No dependents found
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Impact Analysis */}
      {impact && (
        <Card className="border-orange-200 dark:border-orange-900">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Target className="h-4 w-4 text-orange-500" />
                Impact Analysis (Blast Radius)
              </span>
              <span className="text-sm font-normal text-muted-foreground">
                {impact.total_dependents} affected symbols
              </span>
            </CardTitle>
            <CardDescription>
              What would be affected by changes to {symbolName}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {impact.direct_callers.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">Direct Callers ({impact.direct_callers.length})</h4>
                {renderNodeList(impact.direct_callers, 'Direct Callers')}
              </div>
            )}
            {impact.indirect_dependents.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold mb-2">
                  Indirect Dependents ({impact.indirect_dependents.length})
                </h4>
                {renderNodeList(impact.indirect_dependents, 'Indirect Dependents')}
              </div>
            )}
            {impact.total_dependents === 0 && (
              <div className="text-sm text-muted-foreground italic">
                No dependents found - changes to this symbol have minimal impact
              </div>
            )}
            <div className="text-xs text-muted-foreground pt-2 border-t">
              Analysis depth: {impact.max_depth} levels
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
