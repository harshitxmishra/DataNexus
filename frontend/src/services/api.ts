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
  LineageGraph,
  SystemReadiness
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

  async getQualityScorecard(): Promise<{
    total_evaluations: number;
    passed: number;
    failed: number;
    warnings: number;
    pass_rate_percentage: number;
  }> {
    const res = await fetch(`${API_BASE}/data-platform/quality/scorecard`);
    if (!res.ok) throw new Error(`Failed to fetch scorecard: ${res.statusText}`);
    return res.json();
  },

  async getDocumentLineage(documentId: string): Promise<LineageGraph> {
    const res = await fetch(`${API_BASE}/lineage/document/${documentId}`);
    if (!res.ok) throw new Error(`Failed to fetch lineage: ${res.statusText}`);
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

  // Business Intelligence
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
  }
};
