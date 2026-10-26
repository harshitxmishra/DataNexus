import React from 'react';
import { LayoutDashboard, FileText, Search, Database, LineChart, FileCode2 } from 'lucide-react';

export type WorkspaceId = 'overview' | 'documents' | 'search' | 'data_platform' | 'analytics';

interface SidebarProps {
  activeWorkspace: WorkspaceId;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeWorkspace, onSelectWorkspace }) => {
  const navItems = [
    {
      id: 'overview' as WorkspaceId,
      label: 'Overview',
      desc: 'Platform Operations',
      icon: LayoutDashboard,
    },
    {
      id: 'documents' as WorkspaceId,
      label: 'Documents',
      desc: 'Library & Evidence',
      icon: FileText,
    },
    {
      id: 'search' as WorkspaceId,
      label: 'Search & QA',
      desc: 'Lexical, Semantic, RAG',
      icon: Search,
    },
    {
      id: 'data_platform' as WorkspaceId,
      label: 'Data Platform',
      desc: 'ETL, Lineage, Quality',
      icon: Database,
    },
    {
      id: 'analytics' as WorkspaceId,
      label: 'Intelligence (BI)',
      desc: 'Spend & Power BI Views',
      icon: LineChart,
    },
  ];

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-925 flex flex-col shrink-0 select-none">
      <div className="p-3 text-[11px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
        Platform Workspaces
      </div>
      <nav className="flex-1 px-2.5 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeWorkspace === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectWorkspace(item.id)}
              className={`w-full text-left flex items-center space-x-3 px-3 py-2.5 rounded-md transition-all group ${
                isActive
                  ? 'bg-brand-600/15 border border-brand-500/30 text-brand-300 font-medium'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-850/80 border border-transparent'
              }`}
            >
              <Icon
                className={`w-4 h-4 shrink-0 transition-colors ${
                  isActive ? 'text-brand-400' : 'text-slate-500 group-hover:text-slate-300'
                }`}
              />
              <div className="flex-1 truncate">
                <div className="text-sm font-medium leading-tight">{item.label}</div>
                <div className="text-[11px] text-slate-500 truncate leading-normal">{item.desc}</div>
              </div>
            </button>
          );
        })}
      </nav>

      {/* Footer Info */}
      <div className="p-3.5 border-t border-slate-850 text-xs text-slate-500 space-y-1 font-mono">
        <div className="flex items-center justify-between">
          <span>Engine Profile:</span>
          <span className="text-slate-400 font-medium">Production</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Dimensional Model:</span>
          <span className="text-emerald-400 font-medium">Verified Active</span>
        </div>
      </div>
    </aside>
  );
};
