import React, { useEffect, useState } from 'react';
import {
  FileText,
  Upload,
  Search,
  Filter,
  RefreshCw,
  Trash2,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  ArrowUpDown,
  Download,
} from 'lucide-react';
import { api } from '../services/api';
import { DocumentItem } from '../types';

interface DocumentsPageProps {
  onSelectDocument: (docId: string) => void;
}

export const DocumentsPage: React.FC<DocumentsPageProps> = ({ onSelectDocument }) => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      const docs = await api.listDocuments(statusFilter || undefined, undefined, search || undefined);
      setDocuments(docs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadDocuments();
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    try {
      setIsUploading(true);
      setUploadError(null);
      const formData = new FormData();
      formData.append('file', files[0]);
      formData.append('document_type', 'invoice');
      formData.append('process_immediately', 'true');

      const uploaded = await api.uploadDocument(formData);
      setShowUploadModal(false);
      await loadDocuments();
      onSelectDocument(uploaded.id);
    } catch (err: any) {
      setUploadError(err.message || 'File upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, doc: DocumentItem) => {
    e.stopPropagation();
    setDocToDelete(doc);
  };

  const confirmDelete = async () => {
    if (!docToDelete) return;
    try {
      await api.deleteDocument(docToDelete.id);
      setActionFeedback({ type: 'success', message: `Document "${docToDelete.filename}" deleted.` });
      setDocToDelete(null);
      await loadDocuments();
    } catch (e: any) {
      setActionFeedback({ type: 'error', message: `Delete error: ${e.message}` });
      setDocToDelete(null);
    }
  };

  const handleReprocess = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    try {
      setActionFeedback({ type: 'success', message: 'Reprocessing document pipeline...' });
      await api.reprocessDocument(docId);
      setActionFeedback({ type: 'success', message: 'Pipeline reprocessed successfully.' });
      await loadDocuments();
    } catch (e: any) {
      setActionFeedback({ type: 'error', message: `Reprocess error: ${e.message}` });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <span className="badge-status-completed">Completed</span>;
      case 'processing':
        return <span className="badge-status-processing">Processing</span>;
      case 'queued':
        return <span className="badge-status-queued">Queued</span>;
      case 'partially_completed':
        return (
          <span className="bg-amber-950/70 text-amber-400 border border-amber-800 px-2 py-0.5 rounded text-xs font-mono font-medium">
            Partial
          </span>
        );
      case 'failed':
      default:
        return <span className="badge-status-failed">Failed</span>;
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Document Catalog & Library</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Persisted digital invoices, tabular CSV files, page provenance, and extraction states.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadDocuments}
            className="p-2 rounded bg-slate-850 hover:bg-slate-800 border border-slate-700 text-slate-300 transition"
            title="Refresh list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-brand-400' : ''}`} />
          </button>
          <button
            onClick={() => setShowUploadModal(true)}
            className="flex items-center space-x-2 px-3.5 py-2 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium transition shadow-sm"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search documents by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-md pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </form>

        <div className="flex items-center space-x-2 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0 text-xs font-mono">
          <span className="text-slate-500 text-[11px] uppercase mr-1">Status:</span>
          {['', 'completed', 'partially_completed', 'processing', 'failed'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2.5 py-1 rounded text-xs transition ${
                statusFilter === st
                  ? 'bg-brand-600/20 text-brand-300 border border-brand-500/40 font-medium'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:bg-slate-850'
              }`}
            >
              {st === '' ? 'All' : st.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4">Document / File</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-3 text-center">Pages</th>
                <th className="py-3 px-3 text-center">Chunks</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-3 text-right">Confidence</th>
                <th className="py-3 px-4 text-slate-500">SHA-256 Hash</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => onSelectDocument(doc.id)}
                  className="hover:bg-slate-850/50 cursor-pointer transition group"
                >
                  <td className="py-3 px-4 font-semibold text-slate-200">
                    <div className="flex items-center space-x-2">
                      <FileText className="w-4 h-4 text-brand-400 shrink-0" />
                      <span className="truncate max-w-xs group-hover:text-brand-300 transition">
                        {doc.filename}
                      </span>
                      {doc.is_duplicate && (
                        <span className="px-1.5 py-0.2 rounded bg-rose-950/80 text-rose-400 border border-rose-800 text-[10px]">
                          Duplicate
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-slate-400">{doc.document_type}</td>
                  <td className="py-3 px-3 text-center text-slate-300">{doc.page_count}</td>
                  <td className="py-3 px-3 text-center text-sky-400 font-medium">{doc.chunk_count}</td>
                  <td className="py-3 px-4">{getStatusBadge(doc.status)}</td>
                  <td className="py-3 px-3 text-right">
                    {doc.extraction_confidence !== null ? (
                      <span
                        className={`font-medium ${
                          doc.extraction_confidence >= 0.85
                            ? 'text-emerald-400'
                            : doc.extraction_confidence >= 0.70
                            ? 'text-amber-400'
                            : 'text-rose-400'
                        }`}
                      >
                        {Math.round(doc.extraction_confidence * 100)}%
                      </span>
                    ) : (
                      <span className="text-slate-600">—</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-slate-500 text-[11px]">
                    {doc.file_hash.substring(0, 12)}...
                  </td>
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end space-x-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          window.open(`/api/documents/${doc.id}/download`, '_blank');
                        }}
                        className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                        title="Download Original File"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => handleReprocess(e, doc.id)}
                        className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
                        title="Reprocess Pipeline"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => handleDeleteClick(e, doc)}
                        className="p-1.5 rounded hover:bg-rose-950/60 text-slate-500 hover:text-rose-400 transition"
                        title="Safe Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {documents.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500">
                    No documents found matching the filter criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-semibold text-white">Upload Business Document</h3>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-400">
              Upload a digital PDF invoice, receipt, or tabular CSV dataset. Files are verified with SHA-256 hash detection and immediately indexed.
            </p>

            {uploadError && (
              <div className="bg-rose-950/40 border border-rose-800 text-rose-300 p-3 rounded text-xs">
                {uploadError}
              </div>
            )}

            <div className="border-2 border-dashed border-slate-750 hover:border-brand-500 rounded-lg p-6 text-center cursor-pointer transition">
              <input
                type="file"
                id="doc-upload"
                onChange={handleFileUpload}
                accept=".pdf,.csv,.png,.jpg,.jpeg"
                className="hidden"
                disabled={isUploading}
              />
              <label htmlFor="doc-upload" className="cursor-pointer block space-y-2">
                <Upload className="w-8 h-8 text-brand-400 mx-auto" />
                <div className="text-xs text-slate-300 font-medium">
                  {isUploading ? 'Validating and Processing...' : 'Click or drag file to upload'}
                </div>
                <div className="text-[11px] text-slate-500 font-mono">
                  Supported formats: PDF, CSV, PNG, JPG (up to 25MB)
                </div>
              </label>
            </div>
          </div>
        </div>
      )}
      {/* Delete Confirmation Modal */}
      {docToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-sm w-full p-5 space-y-4 shadow-xl font-mono text-xs">
            <div className="flex items-center space-x-2.5 text-rose-400 font-semibold text-sm">
              <AlertCircle className="w-5 h-5 text-rose-500 shrink-0" />
              <span>Confirm Document Deletion</span>
            </div>
            <p className="text-xs text-slate-300 font-sans leading-relaxed">
              Are you sure you want to permanently delete <strong className="text-white">{docToDelete.filename}</strong>? This action will purge its raw file binary, extracted fields, chunks, and lineage anchors.
            </p>
            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setDocToDelete(null)}
                className="px-3 py-1.5 rounded text-slate-400 hover:text-slate-200 border border-slate-800 hover:bg-slate-850 transition"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-3.5 py-1.5 rounded font-semibold bg-rose-600 hover:bg-rose-500 text-white transition shadow-sm"
              >
                Delete Document
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
