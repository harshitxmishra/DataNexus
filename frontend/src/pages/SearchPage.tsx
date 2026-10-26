import React, { useState } from 'react';
import {
  Search as SearchIcon,
  Sparkles,
  Layers,
  FileText,
  Sliders,
  ExternalLink,
  Clock,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ChevronRight,
} from 'lucide-react';
import { api } from '../services/api';
import { SearchResponse, QAResponse } from '../types';

interface SearchPageProps {
  onSelectDocument: (docId: string) => void;
}

export const SearchPage: React.FC<SearchPageProps> = ({ onSelectDocument }) => {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'hybrid' | 'semantic' | 'lexical'>('hybrid');
  const [topK, setTopK] = useState(10);
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // QA state
  const [question, setQuestion] = useState('');
  const [qaResult, setQaResult] = useState<QAResponse | null>(null);
  const [loadingQA, setLoadingQA] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'search' | 'qa'>('search');

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      setLoadingSearch(true);
      setSearchError(null);
      const res = await api.search(query, mode, topK);
      setSearchResults(res);
    } catch (err: any) {
      setSearchError(err.message || 'Search failed');
    } finally {
      setLoadingSearch(false);
    }
  };

  const handleAskQA = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    try {
      setLoadingQA(true);
      setQaError(null);
      const res = await api.askQA(question, 5);
      setQaResult(res);
    } catch (err: any) {
      setQaError(err.message || 'QA request failed');
    } finally {
      setLoadingQA(false);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="border-b border-slate-800 pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
          <span>Search & Intelligence Catalog</span>
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          BM25 full-text lexical matching, 384-dimensional dense vector nearest-neighbour retrieval, and citation-backed question answering.
        </p>
      </div>

      {/* Workspace Switcher */}
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono">
        <button
          onClick={() => setActiveTab('search')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-md transition ${
            activeTab === 'search'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <SearchIcon className="w-3.5 h-3.5" />
          <span>Multi-Modal Retrieval (Lexical / Semantic / Hybrid)</span>
        </button>
        <button
          onClick={() => setActiveTab('qa')}
          className={`flex items-center space-x-2 px-3.5 py-2 rounded-md transition ${
            activeTab === 'qa'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400" />
          <span>Evidence-Backed Question Answering (RAG)</span>
        </button>
      </div>

      {/* TAB 1: RETRIEVAL WORKSPACE */}
      {activeTab === 'search' && (
        <div className="space-y-6">
          {/* Query Bar & Controls */}
          <form onSubmit={handleSearch} className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <SearchIcon className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
                <input
                  type="text"
                  placeholder="Enter keywords, vendor names, line items, or natural concepts (e.g. 'Kubernetes cloud clusters', 'Freight express')..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-md pl-10 pr-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                />
              </div>
              <button
                type="submit"
                disabled={loadingSearch}
                className="px-5 py-2.5 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold font-mono transition shadow-sm flex items-center justify-center space-x-2"
              >
                <span>{loadingSearch ? 'Retrieving...' : 'Execute Query'}</span>
              </button>
            </div>

            {/* Retrieval Parameters */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/80 text-xs font-mono">
              <div className="flex items-center space-x-3">
                <span className="text-slate-500 text-[11px] uppercase">Retrieval Mode:</span>
                {(['hybrid', 'semantic', 'lexical'] as const).map((m) => (
                  <label key={m} className="flex items-center space-x-1.5 cursor-pointer text-slate-300">
                    <input
                      type="radio"
                      name="search-mode"
                      value={m}
                      checked={mode === m}
                      onChange={() => setMode(m)}
                      className="text-brand-500 focus:ring-0"
                    />
                    <span className="capitalize">{m}</span>
                  </label>
                ))}
              </div>

              <div className="flex items-center space-x-2 text-slate-400">
                <span className="text-slate-500 text-[11px] uppercase">Top-K:</span>
                <select
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none"
                >
                  <option value={5}>Top 5</option>
                  <option value={10}>Top 10</option>
                  <option value={20}>Top 20</option>
                </select>
              </div>
            </div>
          </form>

          {/* Search Results Display */}
          {searchError && (
            <div className="bg-rose-950/40 border border-rose-800 text-rose-300 p-4 rounded-lg text-xs">
              {searchError}
            </div>
          )}

          {searchResults && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400 px-1">
                <div>
                  Found <span className="text-white font-bold">{searchResults.total_hits}</span> hit(s) using{' '}
                  <span className="text-brand-300">{searchResults.engine}</span>
                </div>
                <div className="text-[11px] text-slate-500">
                  Active Provider: {searchResults.provider}
                </div>
              </div>

              <div className="space-y-3">
                {searchResults.results.map((hit, idx) => (
                  <div
                    key={hit.chunk_id}
                    onClick={() => onSelectDocument(hit.document_id)}
                    className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg p-4 cursor-pointer transition space-y-2.5 group"
                  >
                    <div className="flex items-center justify-between text-xs font-mono">
                      <div className="flex items-center space-x-2">
                        <span className="text-slate-500 font-bold">#{idx + 1}</span>
                        <FileText className="w-4 h-4 text-brand-400" />
                        <span className="font-semibold text-slate-200 group-hover:text-brand-300 transition">
                          {hit.filename}
                        </span>
                        <span className="text-slate-500">• Page {hit.page_number}</span>
                      </div>

                      {/* Score Inspection */}
                      <div className="flex items-center space-x-3 text-[11px]">
                        <span className="text-slate-400">
                          Lexical: <span className="text-slate-300">{hit.lexical_score}</span>
                        </span>
                        <span className="text-slate-400">
                          Vector: <span className="text-slate-300">{hit.vector_score}</span>
                        </span>
                        <span className="bg-brand-950 text-brand-300 border border-brand-800 px-2 py-0.5 rounded font-bold">
                          Score: {hit.score}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-300 font-sans leading-relaxed bg-slate-950/70 p-3 rounded border border-slate-850">
                      {hit.snippet}
                    </p>
                  </div>
                ))}
                {searchResults.results.length === 0 && (
                  <div className="text-center py-12 text-slate-500 text-xs font-mono">
                    No matching chunks found for this query in the indexed documents.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: QUESTION ANSWERING WORKSPACE */}
      {activeTab === 'qa' && (
        <div className="space-y-6">
          <form onSubmit={handleAskQA} className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
            <div>
              <label className="block text-xs font-mono uppercase text-slate-400 mb-1 font-semibold">
                Ask Questions Over Ingested Documents & Invoices
              </label>
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="text"
                  placeholder="e.g. 'What is the total amount due for Apex Cloud Services and when is it due?'"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-md px-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                />
                <button
                  type="submit"
                  disabled={loadingQA}
                  className="px-6 py-2.5 rounded bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold font-mono transition shadow-sm flex items-center justify-center space-x-2"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                  <span>{loadingQA ? 'Synthesizing...' : 'Answer Question'}</span>
                </button>
              </div>
            </div>
            <div className="text-[11px] text-slate-500 font-mono">
              Note: Answers are strictly derived from verified document excerpts. Material factual claims cite the source file and page number.
            </div>
          </form>

          {qaError && (
            <div className="bg-rose-950/40 border border-rose-800 text-rose-300 p-4 rounded-lg text-xs">
              {qaError}
            </div>
          )}

          {qaResult && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6 shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono text-slate-500 uppercase">Evidence State:</span>
                  <span
                    className={`text-xs font-mono px-2 py-0.5 rounded font-semibold ${
                      qaResult.evidence_status === 'sufficient'
                        ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                        : 'bg-amber-950 text-amber-400 border border-amber-800'
                    }`}
                  >
                    {qaResult.evidence_status.toUpperCase()}
                  </span>
                </div>
                <div className="text-xs font-mono text-slate-500 flex items-center space-x-3">
                  <span>Provider: {qaResult.provider_used}</span>
                  <span>•</span>
                  <span>Latency: {qaResult.latency_ms} ms</span>
                </div>
              </div>

              {/* Synthesized Answer Text */}
              <div className="space-y-2">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold">
                  Synthesized Answer
                </span>
                <div className="text-sm text-slate-100 leading-relaxed font-sans bg-slate-950 p-4 rounded-lg border border-slate-850 whitespace-pre-line">
                  {qaResult.answer}
                </div>
              </div>

              {/* Citations List */}
              {qaResult.citations.length > 0 && (
                <div className="space-y-3 pt-2 border-t border-slate-800">
                  <span className="text-xs font-mono uppercase tracking-wider text-slate-500 font-semibold block">
                    Verified Source Citations ({qaResult.citations.length})
                  </span>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {qaResult.citations.map((c, i) => (
                      <div
                        key={i}
                        onClick={() => onSelectDocument(c.document_id)}
                        className="bg-slate-950 border border-slate-850 hover:border-slate-750 p-3 rounded-lg text-xs font-mono space-y-1.5 cursor-pointer transition group"
                      >
                        <div className="flex items-center justify-between text-brand-300 font-semibold">
                          <span className="truncate group-hover:underline">{c.filename}</span>
                          <span className="text-slate-400">Page {c.page_number}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 font-sans line-clamp-2 italic">
                          "{c.snippet}"
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
