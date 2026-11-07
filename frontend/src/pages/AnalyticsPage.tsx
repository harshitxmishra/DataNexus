import React, { useEffect, useState } from 'react';
import {
  DollarSign,
  TrendingUp,
  AlertTriangle,
  Download,
  Copy,
  Check,
  FileText,
  ExternalLink,
  Layers,
  ArrowUpRight,
  Database,
  Table,
  Eye,
  GitCommit,
  Sparkles,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';
import { api } from '../services/api';
import {
  VendorSpendItem,
  OverdueInvoiceItem,
  SpendTrendItem,
  PowerBiSemanticModel,
  AnalyticalViewItem,
  AnalyticalViewData,
} from '../types';

export const AnalyticsPage: React.FC = () => {
  const [vendorSpend, setVendorSpend] = useState<VendorSpendItem[]>([]);
  const [overdueInvoices, setOverdueInvoices] = useState<OverdueInvoiceItem[]>([]);
  const [spendTrends, setSpendTrends] = useState<SpendTrendItem[]>([]);
  const [duplicates, setDuplicates] = useState<any[]>([]);
  const [semanticModel, setSemanticModel] = useState<PowerBiSemanticModel | null>(null);
  const [analyticalViews, setAnalyticalViews] = useState<AnalyticalViewItem[]>([]);
  const [selectedView, setSelectedView] = useState<string>('v_invoice_spend_by_vendor');
  const [viewPreviewData, setViewPreviewData] = useState<AnalyticalViewData | null>(null);
  const [loadingViewData, setLoadingViewData] = useState(false);

  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [copiedMeasure, setCopiedMeasure] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'analytics' | 'overdue' | 'duplicates' | 'views' | 'powerbi'>('analytics');

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [vs, oi, st, dup, sm, av] = await Promise.all([
          api.getVendorSpend(),
          api.getOverdueInvoices(),
          api.getSpendTrends(),
          api.getDuplicateCandidates(),
          api.getPowerBiSemanticModel(),
          api.listAnalyticalViews(),
        ]);
        setVendorSpend(vs);
        setOverdueInvoices(oi);
        setSpendTrends(st);
        setDuplicates(dup.candidates || []);
        setSemanticModel(sm);
        setAnalyticalViews(av.views || []);

        if (av.views && av.views.length > 0) {
          const defaultView = av.views[0].view_name;
          setSelectedView(defaultView);
          loadViewData(defaultView);
        }
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const loadViewData = async (viewName: string) => {
    try {
      setLoadingViewData(true);
      const data = await api.queryAnalyticalView(viewName, 0, 20);
      setViewPreviewData(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingViewData(false);
    }
  };

  const handleSelectView = (vName: string) => {
    setSelectedView(vName);
    loadViewData(vName);
  };

  const handleCopyConnection = () => {
    const pbiConn = `Server=localhost\nPort=5432\nDatabase=datanexus\nUsername=postgres\nSchema=public\nViews=v_invoice_spend_by_vendor, v_daily_ingestion, v_overdue_invoices, v_data_quality_scorecard, v_processing_performance, v_pipeline_freshness, v_indexing_coverage`;
    navigator.clipboard.writeText(pbiConn);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyMeasure = (measureName: string, expr: string) => {
    navigator.clipboard.writeText(expr);
    setCopiedMeasure(measureName);
    setTimeout(() => setCopiedMeasure(null), 2000);
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Business Intelligence & Financial Analytics</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Curated dimensional fact tables, spend distributions, overdue risk exposure, and Power BI semantic integration.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <a
            href="/api/data-platform/export/invoices"
            className="flex items-center space-x-2 px-3.5 py-2 rounded bg-slate-850 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-mono font-medium transition"
          >
            <Download className="w-3.5 h-3.5 text-brand-400" />
            <span>Export Invoices CSV</span>
          </a>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono overflow-x-auto">
        <button
          onClick={() => setActiveTab('analytics')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'analytics'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Vendor Spend & Trends
        </button>
        <button
          onClick={() => setActiveTab('overdue')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'overdue'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Overdue Exposure ({overdueInvoices.length})
        </button>
        <button
          onClick={() => setActiveTab('duplicates')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'duplicates'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Duplicate Candidates ({duplicates.length})
        </button>
        <button
          onClick={() => setActiveTab('views')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'views'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Curated SQL Views ({analyticalViews.length})
        </button>
        <button
          onClick={() => setActiveTab('powerbi')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'powerbi'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Power BI Semantic Model
        </button>
      </div>

      {/* TAB 1: ANALYTICS & TRENDS */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Vendor Spend Bar Chart */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-3">
              <h3 className="text-xs font-mono uppercase text-slate-400 font-semibold">
                Spend by Vendor (USD Equivalents)
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={vendorSpend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="vendor_name" stroke="#64748b" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px' }}
                      formatter={(val: any) => [`$${val.toLocaleString()}`, 'Spend']}
                    />
                    <Bar dataKey="total_spend" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Spend Trends Line Chart */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-3">
              <h3 className="text-xs font-mono uppercase text-slate-400 font-semibold">
                Monthly Spend Trend (Temporal Trajectory)
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={spendTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '11px' }}
                      formatter={(val: any) => [`$${val.toLocaleString()}`, 'Invoiced']}
                    />
                    <Line type="monotone" dataKey="total_spend" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Vendor Spend Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase text-slate-300 font-semibold">
                Curated Vendor Spend Aggregate Breakdown
              </h3>
              <span className="text-xs font-mono text-slate-400">{vendorSpend.length} Vendors Recorded</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Vendor</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-3 text-right">Invoices</th>
                    <th className="py-3 px-3">Currency</th>
                    <th className="py-3 px-4 text-right">Subtotal</th>
                    <th className="py-3 px-4 text-right">Tax</th>
                    <th className="py-3 px-4 text-right">Total Spend</th>
                    <th className="py-3 px-3 text-right">Confidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {vendorSpend.map((v, i) => (
                    <tr key={i} className="hover:bg-slate-850/40">
                      <td className="py-3 px-4 font-semibold text-slate-200">{v.vendor_name}</td>
                      <td className="py-3 px-4 text-slate-400">{v.vendor_category}</td>
                      <td className="py-3 px-3 text-right text-slate-300">{v.invoice_count}</td>
                      <td className="py-3 px-3 text-slate-400">{v.currency}</td>
                      <td className="py-3 px-4 text-right text-slate-400">${v.total_subtotal.toLocaleString()}</td>
                      <td className="py-3 px-4 text-right text-slate-400">${v.total_tax.toLocaleString()}</td>
                      <td className="py-3 px-4 text-right font-bold text-white">${v.total_spend.toLocaleString()}</td>
                      <td className="py-3 px-3 text-right text-emerald-400">{Math.round(v.avg_confidence * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: OVERDUE EXPOSURE */}
      {activeTab === 'overdue' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase text-slate-300 font-semibold">
                Active Overdue Invoices & Liability Aging
              </h3>
              <span className="text-xs font-mono text-rose-400 font-semibold">{overdueInvoices.length} Overdue</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Invoice #</th>
                    <th className="py-3 px-4">Vendor</th>
                    <th className="py-3 px-3">Currency</th>
                    <th className="py-3 px-4 text-right">Amount</th>
                    <th className="py-3 px-3 text-center">Status</th>
                    <th className="py-3 px-3 text-right">Days Overdue</th>
                    <th className="py-3 px-4">Invoice Date</th>
                    <th className="py-3 px-4">Due Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {overdueInvoices.map((inv, i) => (
                    <tr key={i} className="hover:bg-slate-850/40">
                      <td className="py-3 px-4 font-semibold text-slate-200">{inv.invoice_number}</td>
                      <td className="py-3 px-4 text-slate-300">{inv.vendor_name}</td>
                      <td className="py-3 px-3 text-slate-400">{inv.currency}</td>
                      <td className="py-3 px-4 text-right font-bold text-rose-400">
                        ${inv.total_amount.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-rose-950 text-rose-400 border border-rose-800">
                          {inv.payment_status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right text-rose-300 font-semibold">{inv.days_overdue} days</td>
                      <td className="py-3 px-4 text-slate-400">{inv.invoice_date}</td>
                      <td className="py-3 px-4 text-slate-400">{inv.due_date || '—'}</td>
                    </tr>
                  ))}
                  {overdueInvoices.length === 0 && (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-500">
                        No overdue invoices detected. All payment obligations are current.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: DUPLICATE CANDIDATES */}
      {activeTab === 'duplicates' && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-xs font-mono uppercase text-slate-300 font-semibold">
              SHA-256 Hash Duplicate Detection Audit
            </h3>
            <span className="text-xs font-mono text-slate-400">{duplicates.length} Collisions</span>
          </div>
          <div className="divide-y divide-slate-800">
            {duplicates.map((dup, i) => (
              <div key={i} className="py-3 text-xs font-mono flex items-center justify-between">
                <div>
                  <span className="text-slate-200 font-semibold">{dup.filename}</span>
                  <div className="text-slate-500 text-[11px]">Hash: {dup.file_hash}</div>
                </div>
                <span className="bg-rose-950 text-rose-400 border border-rose-800 px-2 py-0.5 rounded text-[11px]">
                  Duplicate of ID: {dup.duplicate_of_id?.substring(0, 8)}
                </span>
              </div>
            ))}
            {duplicates.length === 0 && (
              <div className="py-6 text-center text-slate-500 text-xs font-mono">
                No duplicate document hash collisions detected. All files are unique across the content store.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: CURATED SQL VIEWS EXPLORER */}
      {activeTab === 'views' && (
        <div className="space-y-6 font-mono text-xs">
          {/* Views Catalog */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {analyticalViews.map((v) => (
              <button
                key={v.view_name}
                onClick={() => handleSelectView(v.view_name)}
                className={`p-3.5 rounded-lg border text-left transition space-y-1.5 ${
                  selectedView === v.view_name
                    ? 'bg-brand-950/80 border-brand-500/60 shadow-sm'
                    : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-slate-400 text-[10px] uppercase font-semibold">{v.domain}</span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">
                    {v.row_count} rows
                  </span>
                </div>
                <div className="font-semibold text-slate-200 text-xs truncate">{v.view_name}</div>
                <div className="text-[11px] text-slate-500 line-clamp-2">{v.description}</div>
              </button>
            ))}
          </div>

          {/* Live Data Preview */}
          {viewPreviewData && (
            <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-white text-xs">
                    Live View Query: <span className="text-emerald-400">{viewPreviewData.view_name}</span>
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">{viewPreviewData.description}</p>
                </div>
                <span className="text-slate-400 text-xs">
                  Showing {viewPreviewData.returned_rows} of {viewPreviewData.total_rows} rows
                </span>
              </div>

              {loadingViewData ? (
                <div className="py-12 text-center text-slate-500">Querying analytical view...</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                      <tr>
                        {viewPreviewData.columns.map((col) => (
                          <th key={col} className="py-2.5 px-4 whitespace-nowrap">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {viewPreviewData.data.map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-850/40">
                          {viewPreviewData.columns.map((col) => (
                            <td key={col} className="py-2 px-4 whitespace-nowrap text-slate-300">
                              {row[col] !== null && row[col] !== undefined ? String(row[col]) : '—'}
                            </td>
                          ))}
                        </tr>
                      ))}
                      {viewPreviewData.data.length === 0 && (
                        <tr>
                          <td colSpan={viewPreviewData.columns.length} className="py-8 text-center text-slate-500">
                            No rows currently stored in this analytical view.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 5: POWER BI SEMANTIC MODEL */}
      {activeTab === 'powerbi' && semanticModel && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6 max-w-5xl font-mono text-xs">
          {/* Header & Connection Copy */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-4 gap-3">
            <div>
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <span>{semanticModel.dataset_name}</span>
              </h3>
              <p className="text-xs text-slate-400 font-sans mt-0.5">
                {semanticModel.architecture} • Native DirectQuery & Import Mode Supported
              </p>
            </div>
            <button
              onClick={handleCopyConnection}
              className="flex items-center space-x-2 px-3 py-1.5 rounded bg-brand-600 hover:bg-brand-500 text-white transition text-xs font-semibold self-start sm:self-auto"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied Parameters' : 'Copy Connection String'}</span>
            </button>
          </div>

          {/* Connection Parameters Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-2">
              <span className="text-slate-500 uppercase text-[10px] font-bold">PostgreSQL Direct Parameters:</span>
              <div className="text-slate-300 space-y-1">
                <div>Server: <span className="text-white">{semanticModel.connection_parameters.server}</span></div>
                <div>Database: <span className="text-white">{semanticModel.connection_parameters.database}</span></div>
                <div>Schema: <span className="text-white">{semanticModel.connection_parameters.schema}</span></div>
                <div>Authentication: <span className="text-white">{semanticModel.connection_parameters.authentication}</span></div>
              </div>
            </div>

            <div className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-2">
              <span className="text-slate-500 uppercase text-[10px] font-bold">Curated Analytical SQL Views:</span>
              <div className="text-slate-300 space-y-1">
                {semanticModel.curated_views.map((v) => (
                  <div key={v}>• <span className="text-emerald-400">{v}</span></div>
                ))}
              </div>
            </div>
          </div>

          {/* Star-Schema Entity Relationships Table */}
          <div className="space-y-3">
            <span className="text-slate-400 uppercase text-[11px] font-bold">Star-Schema Dimensional Relationships</span>
            <div className="bg-slate-950 rounded-lg border border-slate-850 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900 text-slate-400 border-b border-slate-800 text-[10px] uppercase">
                  <tr>
                    <th className="py-2.5 px-3">From Table</th>
                    <th className="py-2.5 px-3">From Column</th>
                    <th className="py-2.5 px-3">To Table</th>
                    <th className="py-2.5 px-3">To Column</th>
                    <th className="py-2.5 px-3">Cardinality</th>
                    <th className="py-2.5 px-3">State</th>
                    <th className="py-2.5 px-3">Cross Filter</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-850">
                  {semanticModel.relationships.map((rel, idx) => (
                    <tr key={idx} className="hover:bg-slate-900/50">
                      <td className="py-2 px-3 font-semibold text-slate-200">{rel.from_table}</td>
                      <td className="py-2 px-3 text-slate-400">{rel.from_column}</td>
                      <td className="py-2 px-3 font-semibold text-emerald-400">{rel.to_table}</td>
                      <td className="py-2 px-3 text-slate-400">{rel.to_column}</td>
                      <td className="py-2 px-3 text-slate-300">{rel.cardinality}</td>
                      <td className="py-2 px-3">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${rel.is_active ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-850 text-slate-400'}`}>
                          {rel.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-400">{rel.cross_filter_direction}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Recommended DAX Measures Library */}
          <div className="space-y-3">
            <span className="text-slate-400 uppercase text-[11px] font-bold">Curated DAX Measure Catalog</span>
            <div className="space-y-2.5">
              {semanticModel.dax_measures.map((m) => (
                <div key={m.name} className="bg-slate-950 p-3 rounded-lg border border-slate-850 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="text-white font-semibold">{m.name}</span>
                      <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 text-[10px]">
                        {m.display_folder}
                      </span>
                      <span className="text-slate-500 text-[10px]">Format: {m.format_string}</span>
                    </div>
                    <button
                      onClick={() => handleCopyMeasure(m.name, m.expression)}
                      className="flex items-center space-x-1 px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-[11px] transition"
                    >
                      {copiedMeasure === m.name ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedMeasure === m.name ? 'Copied' : 'Copy DAX'}</span>
                    </button>
                  </div>
                  <pre className="text-[11px] text-brand-300 font-mono bg-slate-900/80 p-2 rounded overflow-x-auto">
                    {m.expression}
                  </pre>
                  <p className="text-[11px] text-slate-500 font-sans">{m.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
