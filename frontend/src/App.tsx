import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Sidebar, WorkspaceId } from './components/Sidebar';
import { OverviewPage } from './pages/OverviewPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { DocumentDetailPage } from './pages/DocumentDetailPage';
import { SearchPage } from './pages/SearchPage';
import { DataPlatformPage } from './pages/DataPlatformPage';
import { AnalyticsPage } from './pages/AnalyticsPage';

export const App: React.FC = () => {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>('overview');
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId);
  };

  const handleBackToDocuments = () => {
    setSelectedDocumentId(null);
    setActiveWorkspace('documents');
  };

  const handleNavigateToLineage = (docId: string) => {
    setSelectedDocumentId(null);
    setActiveWorkspace('data_platform');
  };

  const handleSelectWorkspace = (ws: WorkspaceId) => {
    setSelectedDocumentId(null);
    setActiveWorkspace(ws);
  };

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100 flex flex-col font-sans">
      <Navbar />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeWorkspace={activeWorkspace} onSelectWorkspace={handleSelectWorkspace} />

        <main className="flex-1 overflow-y-auto bg-[#070b12]">
          {selectedDocumentId ? (
            <DocumentDetailPage
              documentId={selectedDocumentId}
              onBack={handleBackToDocuments}
              onNavigateToLineage={handleNavigateToLineage}
            />
          ) : (
            <>
              {activeWorkspace === 'overview' && (
                <OverviewPage onNavigate={(ws) => handleSelectWorkspace(ws as WorkspaceId)} />
              )}
              {activeWorkspace === 'documents' && (
                <DocumentsPage onSelectDocument={handleSelectDocument} />
              )}
              {activeWorkspace === 'search' && (
                <SearchPage onSelectDocument={handleSelectDocument} />
              )}
              {activeWorkspace === 'data_platform' && <DataPlatformPage />}
              {activeWorkspace === 'analytics' && <AnalyticsPage />}
            </>
          )}
        </main>
      </div>
    </div>
  );
};

export default App;
