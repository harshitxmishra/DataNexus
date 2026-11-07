import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  FileText,
  Clock,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Layers,
  Search,
  ExternalLink,
  Download,
  RefreshCw,
  GitBranch,
} from 'lucide-react';
import { api } from '../services/api';
import { DocumentDetail, ExtractedField, DocumentChunk, StageEvent } from '../types';

interface DocumentDetailPageProps {
  documentId: string;
  onBack: () => void;
  onNavigateToLineage: (docId: string) => void;
}

export const DocumentDetailPage: React.FC<DocumentDetailPageProps> = ({
  documentId,
  onBack,
  onNavigateToLineage,
}) => {
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<ExtractedField | null>(null);
  const [activeTab, setActiveTab] = useState<'fields' | 'line_items' | 'chunks' | 'stages'>('fields');
  const [sseConnected, setSseConnected] = useState(false);
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [streamingStatus, setStreamingStatus] = useState<string | null>(null);

  const loadDocument = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getDocument(documentId);
      setDoc(data);
      if (data.extracted_fields.length > 0) {
        setSelectedField(data.extracted_fields[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load document details');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocument();

    const unsubscribe = api.subscribeDocumentEvents(
      documentId,
      (ev) => {
        setSseConnected(true);
        if (ev.type === 'stage_event') {
          setStreamingStatus(`Stage: ${ev.data.stage} (${ev.data.status})`);
        } else if (ev.type === 'pipeline_completed') {
          setIsReprocessing(false);
          setStreamingStatus('Pipeline completed');
          loadDocument();
        } else if (ev.type === 'pipeline_failed') {
          setIsReprocessing(false);
          setStreamingStatus(`Pipeline failed: ${ev.data.error_message}`);
          loadDocument();
        }
      },
      () => {
        setSseConnected(false);
      }
    );

    return () => {
      unsubscribe();
    };
  }, [documentId]);

  const handleReprocess = async () => {
    try {
      setIsReprocessing(true);
      setActiveTab('stages');
      setStreamingStatus('Triggering pipeline re-execution...');
      await api.reprocessDocument(documentId);
    } catch (err: any) {
      setError(err.message || 'Reprocessing failed');
      setIsReprocessing(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 space-y-6 animate-pulse max-w-7xl mx-auto">
        <div className="h-6 w-32 bg-slate-800 rounded"></div>
        <div className="h-10 w-96 bg-slate-800 rounded"></div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="h-96 bg-slate-900 rounded-lg"></div>
          <div className="h-96 bg-slate-900 rounded-lg"></div>
        </div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <button onClick={onBack} className="flex items-center space-x-1.5 text-xs text-slate-400 hover:text-white mb-4">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Library</span>
        </button>
        <div className="bg-rose-950/40 border border-rose-800 text-rose-300 p-4 rounded-lg">
          {error || 'Document not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Top Header Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div className="space-y-1">
          <button
            onClick={onBack}
            className="flex items-center space-x-1 text-xs font-mono text-slate-400 hover:text-brand-300 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Documents Catalog</span>
          </button>
          <div className="flex items-center space-x-3 pt-1">
            <h1 className="text-xl font-bold tracking-tight text-white">{doc.filename}</h1>
            <span className="badge-status-completed">{doc.status}</span>
            <span className="text-xs font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
              v{doc.version}
            </span>
            {sseConnected && (
              <span className="flex items-center space-x-1.5 px-2 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-[10px] font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>SSE Connected</span>
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleReprocess}
            disabled={isReprocessing}
            className="flex items-center space-x-2 px-3 py-1.5 rounded bg-slate-850 hover:bg-slate-800 disabled:opacity-50 border border-slate-700 text-xs font-mono text-amber-300 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isReprocessing ? 'animate-spin text-amber-400' : 'text-amber-400'}`} />
            <span>{isReprocessing ? 'Reprocessing...' : 'Reprocess Pipeline'}</span>
          </button>
          <button
            onClick={() => onNavigateToLineage(doc.id)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded bg-slate-850 hover:bg-slate-800 border border-slate-700 text-xs font-mono text-brand-300 transition"
          >
            <GitBranch className="w-3.5 h-3.5 text-brand-400" />
            <span>Trace Ingestion Lineage</span>
          </button>
          <button
            onClick={() => window.open(`/api/documents/${doc.id}/download`, '_blank')}
            className="flex items-center space-x-2 px-3 py-1.5 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download Source</span>
          </button>
        </div>
      </div>

      {streamingStatus && (
        <div className="flex items-center justify-between px-4 py-2.5 rounded-lg border border-brand-500/30 bg-brand-950/20 text-brand-200 text-xs font-mono">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-brand-400 animate-ping"></span>
            <span>{streamingStatus}</span>
          </div>
          <button
            onClick={() => setStreamingStatus(null)}
            className="text-slate-400 hover:text-slate-200 text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Signature Investigation Workspace Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Panel: Extracted Fields & Structured Entities (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Navigation Tabs */}
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono">
            <button
              onClick={() => setActiveTab('fields')}
              className={`px-3 py-1.5 rounded-md transition ${
                activeTab === 'fields'
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-medium'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Extracted Fields ({doc.extracted_fields.length})
            </button>
            <button
              onClick={() => setActiveTab('line_items')}
              className={`px-3 py-1.5 rounded-md transition ${
                activeTab === 'line_items'
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-medium'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Invoice Line Items ({doc.line_items.length})
            </button>
            <button
              onClick={() => setActiveTab('chunks')}
              className={`px-3 py-1.5 rounded-md transition ${
                activeTab === 'chunks'
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-medium'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Search Chunks ({doc.chunks.length})
            </button>
            <button
              onClick={() => setActiveTab('stages')}
              className={`px-3 py-1.5 rounded-md transition ${
                activeTab === 'stages'
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-medium'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Pipeline Stages ({doc.stage_events.length})
            </button>
          </div>

          {/* TAB 1: Fields Inspector */}
          {activeTab === 'fields' && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
              <div className="p-3 bg-slate-850/60 border-b border-slate-800 text-xs font-mono text-slate-400">
                Click any extracted field below to inspect its supporting source page evidence and extraction offsets.
              </div>
              <div className="divide-y divide-slate-800/80">
                {doc.extracted_fields.map((field) => {
                  const isSelected = selectedField?.id === field.id;
                  return (
                    <div
                      key={field.id}
                      onClick={() => setSelectedField(field)}
                      className={`p-3.5 text-xs font-mono cursor-pointer transition flex items-center justify-between ${
                        isSelected
                          ? 'bg-brand-600/15 border-l-2 border-brand-400'
                          : 'hover:bg-slate-850/50'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="text-slate-400 uppercase text-[10px] tracking-wider font-semibold">
                          {field.field_name.replace('_', ' ')}
                        </div>
                        <div className="text-sm font-semibold text-white">
                          {field.normalized_value || field.field_value}
                        </div>
                      </div>

                      <div className="flex items-center space-x-3 text-right">
                        <div className="text-[11px] text-slate-400">
                          <div>Page {field.page_number}</div>
                          <div className="text-[10px] text-slate-500">{field.extraction_method}</div>
                        </div>
                        <div className="font-semibold">
                          {field.confidence ? (
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] ${
                                field.confidence >= 0.85
                                  ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800'
                                  : 'bg-amber-950/80 text-amber-400 border border-amber-800'
                              }`}
                            >
                              {Math.round(field.confidence * 100)}%
                            </span>
                          ) : (
                            <span className="text-slate-500">—</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 2: Line Items */}
          {activeTab === 'line_items' && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-850 text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">#</th>
                    <th className="py-2.5 px-3">Description</th>
                    <th className="py-2.5 px-3 text-right">Qty</th>
                    <th className="py-2.5 px-3 text-right">Unit Price</th>
                    <th className="py-2.5 px-3 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {doc.line_items.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-850/40">
                      <td className="py-2.5 px-3 text-slate-500">{item.line_number}</td>
                      <td className="py-2.5 px-3 text-slate-200 font-medium">{item.description}</td>
                      <td className="py-2.5 px-3 text-right text-slate-400">{item.quantity}</td>
                      <td className="py-2.5 px-3 text-right text-slate-400">{item.unit_price.toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-right font-semibold text-white">
                        {item.amount.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                  {doc.line_items.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-500">
                        No individual line items parsed for this document.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* TAB 3: Search Chunks */}
          {activeTab === 'chunks' && (
            <div className="space-y-3">
              {doc.chunks.map((chunk) => (
                <div key={chunk.id} className="bg-slate-900 border border-slate-800 rounded-lg p-3.5 space-y-2 text-xs font-mono">
                  <div className="flex items-center justify-between text-slate-400 border-b border-slate-800/80 pb-1.5 text-[11px]">
                    <span className="text-brand-400 font-semibold">Chunk #{chunk.chunk_index}</span>
                    <span>Page {chunk.page_number} • Offsets [{chunk.start_char}..{chunk.end_char}]</span>
                    <span className="text-emerald-400">Indexed (384d Dense)</span>
                  </div>
                  <p className="text-slate-300 leading-relaxed font-sans text-xs bg-slate-950/60 p-2.5 rounded border border-slate-850">
                    {chunk.content}
                  </p>
                </div>
              ))}
            </div>
          )}

          {/* TAB 4: Pipeline Stages */}
          {activeTab === 'stages' && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
              {doc.stage_events.map((st, idx) => (
                <div key={st.id} className="flex items-start space-x-3 text-xs font-mono border-b border-slate-800/60 pb-3 last:border-0">
                  <div className="mt-0.5">
                    {st.status === 'completed' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-rose-400" />
                    )}
                  </div>
                  <div className="flex-1 space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200 capitalize">
                        {st.stage.replace('_', ' ')}
                      </span>
                      <span className="text-slate-500">{st.duration_ms} ms</span>
                    </div>
                    <div className="text-[11px] text-slate-400">{st.details}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Panel: Supporting Evidence Viewer & Field Provenance (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4 sticky top-20 shadow-panel">
            <div className="border-b border-slate-800 pb-3">
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 font-semibold">
                Field Evidence & Provenance Inspector
              </h3>
            </div>

            {selectedField ? (
              <div className="space-y-4 text-xs font-mono">
                <div>
                  <span className="text-slate-500 uppercase text-[10px]">Field Target:</span>
                  <div className="text-base font-bold text-brand-300 mt-0.5">
                    {selectedField.field_name.replace('_', ' ')}
                  </div>
                </div>

                <div>
                  <span className="text-slate-500 uppercase text-[10px]">Extracted Value:</span>
                  <div className="text-sm font-semibold text-white bg-slate-850 p-2 rounded mt-0.5 border border-slate-750">
                    {selectedField.normalized_value || selectedField.field_value}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="bg-slate-950 p-2 rounded border border-slate-850">
                    <span className="text-slate-500 block">Source Page:</span>
                    <span className="text-slate-200 font-semibold">Page {selectedField.page_number}</span>
                  </div>
                  <div className="bg-slate-950 p-2 rounded border border-slate-850">
                    <span className="text-slate-500 block">Character Offsets:</span>
                    <span className="text-slate-200 font-semibold">
                      [{selectedField.start_char ?? 0}..{selectedField.end_char ?? 0}]
                    </span>
                  </div>
                </div>

                {/* Supporting Text Citation Box */}
                <div>
                  <span className="text-slate-500 uppercase text-[10px] block mb-1">
                    Supporting Text Excerpt (Verifiable Evidence):
                  </span>
                  <div className="p-3 rounded bg-brand-950/20 border border-brand-500/30 text-slate-200 leading-relaxed font-sans text-xs italic">
                    "{selectedField.supporting_text || selectedField.field_value}"
                  </div>
                </div>

                <div className="border-t border-slate-850 pt-3 flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Extraction Method:</span>
                  <span className="text-slate-300 font-semibold">{selectedField.extraction_method}</span>
                </div>

                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Validation Status:</span>
                  <span className="text-emerald-400 font-semibold uppercase">{selectedField.validation_status}</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500 text-xs">
                Select an extracted field to inspect its evidence provenance.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
