/**
 * Workflow Explorer component for Phase 8.
 * 
 * Displays deterministic application workflows derived from static analysis.
 * Shows execution flow from API endpoints or symbols through the codebase.
 */
'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getEndpointWorkflow, getSymbolWorkflow, APIError } from '@/lib/api';
import type { WorkflowResponse, WorkflowNode, WorkflowEdge } from '@/types/repository';

interface WorkflowExplorerProps {
  repositoryId: string;
  endpointId?: string;
  symbolId?: string;
  initialDepth?: number;
}

interface WorkflowTreeNode {
  node: WorkflowNode;
  children: WorkflowTreeNode[];
  visited: boolean; // To handle cycles
}

export default function WorkflowExplorer({ 
  repositoryId, 
  endpointId, 
  symbolId,
  initialDepth = 5 
}: WorkflowExplorerProps) {
  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [depth, setDepth] = useState(initialDepth);
  const [includeCallers, setIncludeCallers] = useState(false);
  const [direction, setDirection] = useState<'downstream' | 'upstream' | 'both'>('downstream');
  
  useEffect(() => {
    if (endpointId || symbolId) {
      loadWorkflow();
    }
  }, [endpointId, symbolId, depth, includeCallers, direction]);
  
  const loadWorkflow = async () => {
    setLoading(true);
    setError(null);
    
    try {
      let data: WorkflowResponse;
      
      if (endpointId) {
        data = await getEndpointWorkflow(repositoryId, endpointId, depth, includeCallers);
      } else if (symbolId) {
        data = await getSymbolWorkflow(repositoryId, symbolId, depth, direction);
      } else {
        throw new Error('Either endpointId or symbolId must be provided');
      }
      
      setWorkflow(data);
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.detail || err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load workflow');
      }
    } finally {
      setLoading(false);
    }
  };
  
  const buildTree = (workflow: WorkflowResponse): WorkflowTreeNode | null => {
    if (!workflow || workflow.nodes.length === 0) {
      return null;
    }
    
    // Create a map for quick node lookup
    const nodeMap = new Map<string, WorkflowNode>();
    workflow.nodes.forEach(node => {
      nodeMap.set(node.id, node);
    });
    
    // Create adjacency list for children
    const childrenMap = new Map<string, string[]>();
    workflow.edges.forEach(edge => {
      if (!childrenMap.has(edge.source)) {
        childrenMap.set(edge.source, []);
      }
      childrenMap.get(edge.source)!.push(edge.target);
    });
    
    // Build tree starting from start_node
    const visited = new Set<string>();
    
    const buildNode = (nodeId: string): WorkflowTreeNode | null => {
      const node = nodeMap.get(nodeId);
      if (!node) return null;
      
      const isVisited = visited.has(nodeId);
      const treeNode: WorkflowTreeNode = {
        node,
        children: [],
        visited: isVisited
      };
      
      // If already visited (cycle), don't traverse children
      if (isVisited) {
        return treeNode;
      }
      
      visited.add(nodeId);
      
      // Build children
      const childIds = childrenMap.get(nodeId) || [];
      for (const childId of childIds) {
        const childNode = buildNode(childId);
        if (childNode) {
          treeNode.children.push(childNode);
        }
      }
      
      return treeNode;
    };
    
    return buildNode(workflow.start_node.id);
  };
  
  const renderNode = (treeNode: WorkflowTreeNode, level: number = 0): JSX.Element => {
    const { node, children, visited } = treeNode;
    const indent = level * 24; // 24px per level
    
    return (
      <div key={`${node.id}-${level}`} style={{ marginLeft: `${indent}px` }}>
        <div className="py-2 border-l-2 border-gray-300 pl-4 mb-1">
          {/* Node Type Badge */}
          <div className="flex items-start gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${getNodeTypeColor(node.type)}`}>
              {node.type}
            </span>
            
            <div className="flex-1">
              {/* Node Name */}
              <div className="font-mono font-semibold text-sm">
                {node.name}
              </div>
              
              {/* Symbol Type */}
              {node.symbol_type && (
                <span className="text-xs text-gray-500 ml-2">
                  ({node.symbol_type})
                </span>
              )}
              
              {/* File and Line Info */}
              {node.file_path && (
                <div className="text-xs text-gray-600 mt-1">
                  <span className="font-medium">File:</span> {node.file_path}
                  {node.start_line && node.end_line && (
                    <span className="ml-2">
                      <span className="font-medium">Lines:</span> {node.start_line}-{node.end_line}
                    </span>
                  )}
                </div>
              )}
              
              {/* Cycle indicator */}
              {visited && (
                <div className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                  <span>↻</span>
                  <span>Already visited (cycle detected)</span>
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Render children only if not a visited node */}
        {!visited && children.length > 0 && (
          <div>
            {children.map((child, idx) => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };
  
  const getNodeTypeColor = (type: string): string => {
    switch (type) {
      case 'endpoint': return 'bg-blue-100 text-blue-800';
      case 'symbol': return 'bg-green-100 text-green-800';
      case 'file': return 'bg-yellow-100 text-yellow-800';
      case 'external_module': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };
  
  if (loading) {
    return (
      <Card className="p-6">
        <p className="text-center text-gray-500">Loading workflow...</p>
      </Card>
    );
  }
  
  if (error) {
    return (
      <Card className="p-6">
        <p className="text-center text-red-600">Error: {error}</p>
        <div className="text-center mt-4">
          <Button onClick={loadWorkflow}>Retry</Button>
        </div>
      </Card>
    );
  }
  
  if (!workflow) {
    return (
      <Card className="p-6">
        <p className="text-center text-gray-500">No workflow data available</p>
      </Card>
    );
  }
  
  const tree = buildTree(workflow);
  
  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card className="p-4">
        <div className="flex gap-4 items-center flex-wrap">
          <div>
            <label className="text-sm font-medium mr-2">Depth:</label>
            <select
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="border rounded px-2 py-1"
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(d => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          
          {endpointId && (
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="includeCallers"
                checked={includeCallers}
                onChange={(e) => setIncludeCallers(e.target.checked)}
                className="rounded"
              />
              <label htmlFor="includeCallers" className="text-sm font-medium">
                Include upstream callers
              </label>
            </div>
          )}
          
          {symbolId && (
            <div>
              <label className="text-sm font-medium mr-2">Direction:</label>
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value as any)}
                className="border rounded px-2 py-1"
              >
                <option value="downstream">Downstream (calls)</option>
                <option value="upstream">Upstream (callers)</option>
                <option value="both">Both</option>
              </select>
            </div>
          )}
          
          <div className="ml-auto text-sm text-gray-600">
            {workflow.node_count} nodes, {workflow.edge_count} edges
          </div>
        </div>
      </Card>
      
      {/* Truncation Warning */}
      {workflow.truncated && (
        <Card className="p-4 bg-amber-50 border-amber-200">
          <div className="flex items-start gap-2">
            <span className="text-amber-600 font-bold">⚠</span>
            <div>
              <p className="font-semibold text-amber-900">Workflow Truncated</p>
              <p className="text-sm text-amber-800 mt-1">
                This workflow exceeded the configured analysis limit. The displayed paths may not represent 
                the complete statically discoverable workflow.
              </p>
              {workflow.truncation_reason && (
                <p className="text-xs text-amber-700 mt-1">
                  Reason: {workflow.truncation_reason}
                </p>
              )}
            </div>
          </div>
        </Card>
      )}
      
      {/* Workflow Tree */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-4">
          Application Workflow
        </h3>
        
        <div className="bg-gray-50 p-4 rounded overflow-x-auto">
          {tree ? (
            renderNode(tree)
          ) : (
            <p className="text-center text-gray-500">No workflow information was found for this item.</p>
          )}
        </div>
        
        <div className="mt-4 text-xs text-gray-500 border-t pt-3">
          <p className="font-semibold">Note:</p>
          <p>
            This workflow represents POSSIBLE statically discoverable execution paths based on code analysis. 
            Actual runtime behavior may differ due to dynamic dispatch, reflection, dependency injection, 
            or runtime configuration.
          </p>
        </div>
      </Card>
    </div>
  );
}
