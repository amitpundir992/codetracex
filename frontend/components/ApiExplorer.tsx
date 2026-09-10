/**
 * API Explorer component for Phase 7.
 * 
 * Displays detected API endpoints with filtering, details, and dependency information.
 */
'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getRepositoryEndpoints, getEndpointDetails, getEndpointDependencies, APIError } from '@/lib/api';
import type { ApiEndpointSummary, ApiEndpointDetail, ApiEndpointDependencies } from '@/types/repository';

interface ApiExplorerProps {
  repositoryId: string;
}

export default function ApiExplorer({ repositoryId }: ApiExplorerProps) {
  const [endpoints, setEndpoints] = useState<ApiEndpointSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<ApiEndpointDetail | null>(null);
  const [dependencies, setDependencies] = useState<ApiEndpointDependencies | null>(null);
  const [methodFilter, setMethodFilter] = useState<string>('');
  const [frameworkFilter, setFrameworkFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  
  useEffect(() => {
    loadEndpoints();
  }, [repositoryId, page, methodFilter, frameworkFilter]);
  
  const loadEndpoints = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await getRepositoryEndpoints(
        repositoryId,
        page,
        20,
        methodFilter || undefined,
        frameworkFilter || undefined
      );
      
      setEndpoints(response.items);
      setTotalPages(response.total_pages);
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.detail || err.message);
      } else {
        setError('Failed to load API endpoints');
      }
    } finally {
      setLoading(false);
    }
  };
  
  const loadEndpointDetails = async (endpointId: string) => {
    try {
      const [details, deps] = await Promise.all([
        getEndpointDetails(repositoryId, endpointId),
        getEndpointDependencies(repositoryId, endpointId)
      ]);
      
      setSelectedEndpoint(details);
      setDependencies(deps);
    } catch (err) {
      console.error('Failed to load endpoint details:', err);
    }
  };
  
  const getMethodColor = (method: string): string => {
    switch (method.toUpperCase()) {
      case 'GET': return 'bg-blue-100 text-blue-800';
      case 'POST': return 'bg-green-100 text-green-800';
      case 'PUT': return 'bg-yellow-100 text-yellow-800';
      case 'PATCH': return 'bg-orange-100 text-orange-800';
      case 'DELETE': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };
  
  if (loading && endpoints.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-center text-gray-500">Loading API endpoints...</p>
      </Card>
    );
  }
  
  if (error) {
    return (
      <Card className="p-6">
        <p className="text-center text-red-600">Error: {error}</p>
        <div className="text-center mt-4">
          <Button onClick={loadEndpoints}>Retry</Button>
        </div>
      </Card>
    );
  }
  
  if (endpoints.length === 0 && !loading) {
    return (
      <Card className="p-6">
        <p className="text-center text-gray-500">No API endpoints were detected for this analysis.</p>
      </Card>
    );
  }
  
  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card className="p-4">
        <div className="flex gap-4">
          <div>
            <label className="text-sm font-medium">Method:</label>
            <select
              value={methodFilter}
              onChange={(e) => { setMethodFilter(e.target.value); setPage(1); }}
              className="ml-2 border rounded px-2 py-1"
            >
              <option value="">All</option>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="PATCH">PATCH</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>
          
          <div>
            <label className="text-sm font-medium">Framework:</label>
            <select
              value={frameworkFilter}
              onChange={(e) => { setFrameworkFilter(e.target.value); setPage(1); }}
              className="ml-2 border rounded px-2 py-1"
            >
              <option value="">All</option>
              <option value="fastapi">FastAPI</option>
              <option value="flask">Flask</option>
              <option value="express">Express</option>
            </select>
          </div>
        </div>
      </Card>
      
      {/* Endpoint List */}
      <Card className="p-4">
        <h3 className="text-lg font-semibold mb-4">API Endpoints ({endpoints.length})</h3>
        
        <div className="space-y-2">
          {endpoints.map((endpoint) => (
            <div
              key={endpoint.id}
              className="border rounded p-3 hover:bg-gray-50 cursor-pointer"
              onClick={() => loadEndpointDetails(endpoint.id)}
            >
              <div className="flex items-center gap-3">
                <span className={`px-2 py-1 rounded text-xs font-semibold ${getMethodColor(endpoint.method)}`}>
                  {endpoint.method}
                </span>
                <span className="font-mono font-semibold">{endpoint.path}</span>
                <span className="text-sm text-gray-500">{endpoint.framework}</span>
              </div>
              
              <div className="mt-2 text-sm text-gray-600">
                <span>Handler: {endpoint.handler_name || 'N/A'}</span>
                <span className="ml-4">File: {endpoint.file_path}</span>
              </div>
            </div>
          ))}
        </div>
        
        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex justify-center gap-2 mt-4">
            <Button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="px-4 py-2">
              Page {page} of {totalPages}
            </span>
            <Button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        )}
      </Card>
      
      {/* Endpoint Details */}
      {selectedEndpoint && (
        <Card className="p-4">
          <h3 className="text-lg font-semibold mb-4">Endpoint Details</h3>
          
          <div className="space-y-3">
            <div>
              <span className={`px-2 py-1 rounded text-xs font-semibold ${getMethodColor(selectedEndpoint.method)}`}>
                {selectedEndpoint.method}
              </span>
              <span className="ml-3 font-mono font-semibold text-lg">{selectedEndpoint.path}</span>
            </div>
            
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-semibold">Framework:</span> {selectedEndpoint.framework}
              </div>
              <div>
                <span className="font-semibold">Handler:</span> {selectedEndpoint.handler_name || 'N/A'}
              </div>
              <div>
                <span className="font-semibold">File:</span> {selectedEndpoint.file_path}
              </div>
              <div>
                <span className="font-semibold">Lines:</span> {selectedEndpoint.start_line} - {selectedEndpoint.end_line}
              </div>
            </div>
            
            {selectedEndpoint.handler_symbol && (
              <div className="mt-4">
                <h4 className="font-semibold mb-2">Handler Symbol:</h4>
                <div className="bg-gray-50 p-3 rounded text-sm">
                  <div><span className="font-semibold">Name:</span> {selectedEndpoint.handler_symbol.name}</div>
                  <div><span className="font-semibold">Type:</span> {selectedEndpoint.handler_symbol.type}</div>
                  <div><span className="font-semibold">File:</span> {selectedEndpoint.handler_symbol.file_path}</div>
                </div>
              </div>
            )}
            
            {dependencies && (
              <div className="mt-4">
                <h4 className="font-semibold mb-2">Dependencies:</h4>
                
                {dependencies.dependencies.length > 0 ? (
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-sm font-semibold mb-2">Called by this endpoint:</p>
                    <ul className="text-sm space-y-1">
                      {dependencies.dependencies.map((dep) => (
                        <li key={dep.id} className="ml-4">
                          → {dep.name} <span className="text-gray-500">({dep.file_path})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No downstream dependencies detected</p>
                )}
                
                {dependencies.callers.length > 0 && (
                  <div className="bg-gray-50 p-3 rounded mt-2">
                    <p className="text-sm font-semibold mb-2">Calls this endpoint:</p>
                    <ul className="text-sm space-y-1">
                      {dependencies.callers.map((caller) => (
                        <li key={caller.id} className="ml-4">
                          ← {caller.name} <span className="text-gray-500">({caller.file_path})</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
