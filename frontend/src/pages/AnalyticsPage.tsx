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
import { VendorSpendItem, OverdueInvoiceItem, SpendTrendItem } from '../types';

export const AnalyticsPage: React.FC = () => {
  const [vendorSpend, setVendorSpend] = useState<VendorSpendItem[]>([]);
  const [overdueInvoices, setOverdueInvoices] = useState<OverdueInvoiceItem[]>([]);
  const [spendTrends, setSpendTrends] = useState<SpendTrendItem[]>([]);
  const [duplicates, setDuplicates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'analytics' | 'overdue' | 'duplicates' | 'powerbi'>('analytics');

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [vs, oi, st, dup] = await Promise.all([
          api.getVendorSpend(),
          api.getOverdueInvoices(),
          api.getSpendTrends(),
          api.getDuplicateCandidates(),
        ]);
        setVendorSpend(vs);
        setOverdueInvoices(oi);
        setSpendTrends(st);
        setDuplicates(dup.candidates || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleCopyConnection = () => {
    const pbiConn = `Server=localhost\nPort=5432\nDatabase=datanexus\nUsername=postgres\nSchema=public\nViews=v_invoice_spend_by_vendor, v_daily_ingestion, v_overdue_invoices, v_data_quality_scorecard`;
    navigator.clipboard.writeText(pbiConn);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
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
      <div className="flex items-center space-x-2 border-b border-slate-800 pb-2 text-xs font-mono">
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
          onClick={() => setActiveTab('powerbi')}
          className={`px-3.5 py-1.5 rounded-md transition ${
            activeTab === 'powerbi'
              ? 'bg-brand-600/20 text-brand-300 border border-brand-500/30 font-semibold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Power BI Integration Guide
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
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }}
                    />
                    <Bar dataKey="total_spend" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Spend Trends Line Chart */}
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-lg space-y-3">
              <h3 className="text-xs font-mono uppercase text-slate-400 font-semibold">
                Monthly Invoiced Spend Trend
              </h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={spendTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="period" stroke="#64748b" tick={{ fontSize: 10 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }}
                    />
                    <Line type="monotone" dataKey="total_spend" stroke="#10b981" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Curated Vendor Spend Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
            <div className="p-3 bg-slate-850/60 border-b border-slate-800 flex items-center justify-between text-xs font-mono">
              <span className="text-slate-300 font-semibold">
                Curated Fact View: v_invoice_spend_by_vendor
              </span>
              <span className="text-slate-500">Separated by Currency ISO</span>
            </div>
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 text-[11px] uppercase">
                <tr>
                  <th className="py-3 px-4">Vendor</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-3">Currency</th>
                  <th className="py-3 px-3 text-right">Invoices</th>
                  <th className="py-3 px-4 text-right">Subtotal</th>
                  <th className="py-3 px-4 text-right">Tax</th>
                  <th className="py-3 px-4 text-right">Total Verified Spend</th>
                  <th className="py-3 px-3 text-right">Avg Conf</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {vendorSpend.map((v, i) => (
                  <tr key={i} className="hover:bg-slate-850/40">
                    <td className="py-3 px-4 font-semibold text-slate-200">{v.vendor_name}</td>
                    <td className="py-3 px-4 text-slate-400">{v.vendor_category}</td>
                    <td className="py-3 px-3 text-brand-400 font-bold">{v.currency}</td>
                    <td className="py-3 px-3 text-right text-slate-300">{v.invoice_count}</td>
                    <td className="py-3 px-4 text-right text-slate-400">{v.total_subtotal.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right text-slate-400">{v.total_tax.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right font-bold text-white">
                      {v.total_spend.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-3 text-right text-emerald-400">
                      {Math.round(v.avg_confidence * 100)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: OVERDUE INVOICES */}
      {activeTab === 'overdue' && (
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
            <div className="p-3 bg-slate-850/60 border-b border-slate-800 text-xs font-mono text-amber-400 font-semibold">
              Curated View: v_overdue_invoices (Immediate Cash Flow & Payment Risk)
            </div>
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-850/80 text-slate-400 border-b border-slate-800 text-[11px] uppercase">
                <tr>
                  <th className="py-3 px-4">Invoice #</th>
                  <th className="py-3 px-4">Vendor</th>
                  <th className="py-3 px-3">Currency</th>
                  <th className="py-3 px-4 text-right">Exposure Amount</th>
                  <th className="py-3 px-3 text-center">Days Overdue</th>
                  <th className="py-3 px-4">Invoice Date</th>
                  <th className="py-3 px-4">Due Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {overdueInvoices.map((inv, idx) => (
                  <tr key={idx} className="hover:bg-slate-850/40">
                    <td className="py-3 px-4 font-semibold text-rose-300">{inv.invoice_number}</td>
                    <td className="py-3 px-4 text-slate-200">{inv.vendor_name}</td>
                    <td className="py-3 px-3 text-slate-400">{inv.currency}</td>
                    <td className="py-3 px-4 text-right font-bold text-white">
                      {inv.total_amount.toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span className="bg-rose-950 text-rose-400 border border-rose-800 px-2 py-0.5 rounded text-[11px] font-bold">
                        +{inv.days_overdue} days
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">{inv.invoice_date}</td>
                    <td className="py-3 px-4 text-rose-400 font-medium">{inv.due_date || '—'}</td>
                  </tr>
                ))}
                {overdueInvoices.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-slate-500">
                      No overdue invoice liabilities detected.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: DUPLICATE CANDIDATES */}
      {activeTab === 'duplicates' && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
          <div className="text-xs font-mono text-slate-400">
            Duplicate detection analyzes document SHA-256 byte hashes and business key uniqueness (invoice_number, vendor_name).
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
                No duplicate document hash collisions detected. All files are unique.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: POWER BI GUIDE */}
      {activeTab === 'powerbi' && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-6 max-w-4xl font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-base font-bold text-white">Power BI & External BI Connection Guide</h3>
              <p className="text-xs text-slate-400 font-sans mt-0.5">
                Connect Power BI Desktop directly to DataNexus PostgreSQL curated analytical views.
              </p>
            </div>
            <button
              onClick={handleCopyConnection}
              className="flex items-center space-x-2 px-3 py-1.5 rounded bg-brand-600 hover:bg-brand-500 text-white transition text-xs font-semibold"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied Details' : 'Copy Connection String'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-2">
              <span className="text-slate-500 uppercase text-[10px] font-bold">PostgreSQL Direct Parameters:</span>
              <div className="text-slate-300 space-y-1">
                <div>Server: <span className="text-white">localhost:5432</span></div>
                <div>Database: <span className="text-white">datanexus</span></div>
                <div>Authentication: <span className="text-white">Database Credentials</span></div>
                <div>Connectivity Mode: <span className="text-brand-400">Import or DirectQuery</span></div>
              </div>
            </div>

            <div className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-2">
              <span className="text-slate-500 uppercase text-[10px] font-bold">Curated Analytical SQL Views:</span>
              <div className="text-slate-300 space-y-1">
                <div>• <span className="text-emerald-400">v_invoice_spend_by_vendor</span></div>
                <div>• <span className="text-emerald-400">v_daily_ingestion</span></div>
                <div>• <span className="text-emerald-400">v_processing_performance</span></div>
                <div>• <span className="text-emerald-400">v_overdue_invoices</span></div>
                <div>• <span className="text-emerald-400">v_data_quality_scorecard</span></div>
                <div>• <span className="text-emerald-400">v_pipeline_freshness</span></div>
              </div>
            </div>
          </div>

          <div className="bg-slate-950 p-4 rounded-lg border border-slate-850 space-y-2">
            <span className="text-slate-500 uppercase text-[10px] font-bold">Recommended DAX Measures:</span>
            <pre className="text-[11px] text-slate-300 font-mono bg-slate-900 p-3 rounded overflow-x-auto">
{`Total Invoiced Spend = SUM(v_invoice_spend_by_vendor[total_spend])
Overdue Exposure USD = CALCULATE(SUM(v_overdue_invoices[total_amount]), v_overdue_invoices[currency] = "USD")
Quality Pass Percentage = AVERAGE(v_data_quality_scorecard[pass_percentage])`}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
