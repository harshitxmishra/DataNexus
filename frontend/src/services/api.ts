import {
  DocumentItem,
  DocumentDetail,
  OverviewMetrics,
  VendorSpendItem,
  OverdueInvoiceItem,
  SpendTrendItem,
  ProcessingPerformanceMetric,
  SearchResponse,
  QAResponse,
  PipelineRun,
  DataQualityResult,
  DetailedScorecard,
  LineageGraph,
  SystemReadiness,
  AnalyticalViewItem,
  AnalyticalViewData,
  PowerBiSemanticModel,
  PowerBiMQueriesResponse
} from '../types';

const API_BASE = '/api';

export const api = {
  // System Health
  async getReadiness(): Promise<SystemReadiness> {
    const res = await fetch(`${API_BASE}/health/readiness`);
    if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
    return res.json();
  },

  // Overview Analytics
  async getOverviewMetrics(): Promise<OverviewMetrics> {
    const res = await fetch(`${API_BASE}/analytics/overview`);
    if (!res.ok) throw new Error(`Failed to load overview: ${res.statusText}`);
    return res.json();
  },

  // Documents
  async listDocuments(status?: string, documentType?: string, search?: string): Promise<DocumentItem[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (documentType) params.append('document_type', documentType);
    if (search) params.append('search', search);
    
    const res = await fetch(`${API_BASE}/documents?${params.toString()}`);
    if (!res.ok) throw new Error(`Failed to list documents: ${res.statusText}`);
    return res.json();
  },

  async getDocument(id: string): Promise<DocumentDetail> {
    const res = await fetch(`${API_BASE}/documents/${id}`);
    if (!res.ok) throw new Error(`Failed to get document detail: ${res.statusText}`);
    return res.json();
  },

  async uploadDocument(formData: FormData): Promise<DocumentDetail> {
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async reprocessDocument(id: string): Promise<DocumentDetail> {
    const res = await fetch(`${API_BASE}/documents/${id}/reprocess`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Reprocess failed: ${res.statusText}`);
    return res.json();
  },

  async deleteDocument(id: string): Promise<{ status: string; message: string }> {
    const res = await fetch(`${API_BASE}/documents/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`Delete failed: ${res.statusText}`);
    return res.json();
  },

  // Search & QA
  async search(query: string, mode: string = 'hybrid', topK: number = 10, docType?: string): Promise<SearchResponse> {
    const res = await fetch(`${API_BASE}/search/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, mode, top_k: topK, document_type: docType || undefined }),
    });
    if (!res.ok) throw new Error(`Search failed: ${res.statusText}`);
    return res.json();
  },

  async askQA(question: string, topK: number = 5, docType?: string): Promise<QAResponse> {
    const res = await fetch(`${API_BASE}/search/qa`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, top_k: topK, document_type: docType || undefined }),
    });
    if (!res.ok) throw new Error(`QA failed: ${res.statusText}`);
    return res.json();
  },

  async getSearchStatus(): Promise<{
    active_provider: string;
    elasticsearch_connected: boolean;
    total_chunks_stored: number;
    total_chunks_indexed: number;
    unindexed_outbox_chunks: number;
    supported_modes: string[];
    fallback_active: boolean;
    cluster_info?: any;
  }> {
    const res = await fetch(`${API_BASE}/search/status`);
    if (!res.ok) throw new Error(`Search status failed: ${res.statusText}`);
    return res.json();
  },

  // Data Platform
  async listPipelineRuns(): Promise<PipelineRun[]> {
    const res = await fetch(`${API_BASE}/data-platform/pipeline/runs`);
    if (!res.ok) throw new Error(`Failed to fetch pipeline runs: ${res.statusText}`);
    return res.json();
  },

  async triggerPipeline(): Promise<PipelineRun> {
    const res = await fetch(`${API_BASE}/data-platform/pipeline/run`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Pipeline run failed: ${res.statusText}`);
    return res.json();
  },

  async listQualityResults(status?: string, category?: string): Promise<DataQualityResult[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (category) params.append('rule_category', category);

    const res = await fetch(`${API_BASE}/data-platform/quality/results?${params.toString()}`);
    if (!res.ok) throw new Error(`Failed to fetch quality results: ${res.statusText}`);
    return res.json();
  },

  async getQualityScorecard(): Promise<DetailedScorecard> {
    const res = await fetch(`${API_BASE}/data-platform/quality/scorecard`);
    if (!res.ok) throw new Error(`Failed to fetch scorecard: ${res.statusText}`);
    return res.json();
  },

  async evaluateQuality(documentId?: string): Promise<{
    status: string;
    documents_evaluated: number;
    total_rules_evaluated: number;
    scorecard: DetailedScorecard;
  }> {
    const url = documentId
      ? `${API_BASE}/data-platform/quality/evaluate?document_id=${encodeURIComponent(documentId)}`
      : `${API_BASE}/data-platform/quality/evaluate`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error(`Quality evaluation failed: ${res.statusText}`);
    return res.json();
  },

  async getDocumentLineage(documentId: string, direction: string = 'document', maxDepth: number = 6): Promise<LineageGraph> {
    const params = new URLSearchParams({ direction, max_depth: String(maxDepth) });
    const res = await fetch(`${API_BASE}/lineage/document/${documentId}?${params.toString()}`);
    if (!res.ok) throw new Error(`Failed to fetch lineage: ${res.statusText}`);
    return res.json();
  },

  async getLineageSummary(): Promise<{
    total_nodes: number;
    total_edges: number;
    nodes_by_type: Record<string, number>;
    edges_by_rule: Record<string, number>;
  }> {
    const res = await fetch(`${API_BASE}/lineage/summary`);
    if (!res.ok) throw new Error(`Failed to fetch lineage summary: ${res.statusText}`);
    return res.json();
  },

  async ingestCsv(formData: FormData): Promise<any> {
    const res = await fetch(`${API_BASE}/data-platform/csv/ingest`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(`CSV ingestion failed: ${res.statusText}`);
    return res.json();
  },

  // Business Intelligence & Semantic Models
  async getVendorSpend(): Promise<VendorSpendItem[]> {
    const res = await fetch(`${API_BASE}/analytics/vendor-spend`);
    if (!res.ok) throw new Error(`Failed to load vendor spend: ${res.statusText}`);
    return res.json();
  },

  async getOverdueInvoices(): Promise<OverdueInvoiceItem[]> {
    const res = await fetch(`${API_BASE}/analytics/overdue-invoices`);
    if (!res.ok) throw new Error(`Failed to load overdue invoices: ${res.statusText}`);
    return res.json();
  },

  async getSpendTrends(): Promise<SpendTrendItem[]> {
    const res = await fetch(`${API_BASE}/analytics/spend-trends`);
    if (!res.ok) throw new Error(`Failed to load spend trends: ${res.statusText}`);
    return res.json();
  },

  async getProcessingPerformance(): Promise<ProcessingPerformanceMetric[]> {
    const res = await fetch(`${API_BASE}/analytics/processing-performance`);
    if (!res.ok) throw new Error(`Failed to load processing metrics: ${res.statusText}`);
    return res.json();
  },

  async getDuplicateCandidates(): Promise<{
    total_duplicates_detected: number;
    candidates: any[];
  }> {
    const res = await fetch(`${API_BASE}/analytics/duplicate-candidates`);
    if (!res.ok) throw new Error(`Failed to load duplicates: ${res.statusText}`);
    return res.json();
  },

  async listAnalyticalViews(): Promise<{ views: AnalyticalViewItem[] }> {
    const res = await fetch(`${API_BASE}/analytics/views`);
    if (!res.ok) throw new Error(`Failed to list analytical views: ${res.statusText}`);
    return res.json();
  },

  async queryAnalyticalView(viewName: string, skip: number = 0, limit: number = 50): Promise<AnalyticalViewData> {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    const res = await fetch(`${API_BASE}/analytics/views/${viewName}?${params.toString()}`);
    if (!res.ok) throw new Error(`Failed to query view ${viewName}: ${res.statusText}`);
    return res.json();
  },

  async getPowerBiSemanticModel(): Promise<PowerBiSemanticModel> {
    const res = await fetch(`${API_BASE}/analytics/powerbi/semantic-model`);
    if (!res.ok) throw new Error(`Failed to load Power BI semantic model: ${res.statusText}`);
    return res.json();
  },

  async getPowerBiMQueries(): Promise<PowerBiMQueriesResponse> {
    const res = await fetch(`${API_BASE}/analytics/powerbi/m-queries`);
    if (!res.ok) throw new Error(`Failed to load Power BI M queries: ${res.statusText}`);
    return res.json();
  },

  getExportPowerBiScriptUrl(): string {
    return `${API_BASE}/analytics/powerbi/export-script`;
  },

  // Real-Time Server-Sent Events (SSE) Streaming
  subscribeDocumentEvents(
    documentId: string,
    onEvent: (event: { type: string; data: any }) => void,
    onError?: (err: any) => void
  ): () => void {
    const es = new EventSource(`${API_BASE}/documents/${documentId}/events/stream`);

    const handleMessage = (type: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        onEvent({ type, data });
      } catch (err) {
        console.error(`Failed to parse SSE event (${type}):`, err);
      }
    };

    es.addEventListener('snapshot', handleMessage('snapshot'));
    es.addEventListener('stage_event', handleMessage('stage_event'));
    es.addEventListener('pipeline_completed', handleMessage('pipeline_completed'));
    es.addEventListener('pipeline_failed', handleMessage('pipeline_failed'));

    es.onerror = (err) => {
      if (onError) onError(err);
    };

    return () => {
      es.close();
    };
  },

  subscribePipelineEvents(
    onEvent: (event: { type: string; data: any }) => void,
    onError?: (err: any) => void
  ): () => void {
    const es = new EventSource(`${API_BASE}/documents/events/stream`);

    const handleMessage = (type: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        onEvent({ type, data });
      } catch (err) {
        console.error(`Failed to parse global SSE event (${type}):`, err);
      }
    };

    es.addEventListener('stage_event', handleMessage('stage_event'));
    es.addEventListener('pipeline_completed', handleMessage('pipeline_completed'));
    es.addEventListener('pipeline_failed', handleMessage('pipeline_failed'));

    es.onerror = (err) => {
      if (onError) onError(err);
    };

    return () => {
      es.close();
    };
  }
};
