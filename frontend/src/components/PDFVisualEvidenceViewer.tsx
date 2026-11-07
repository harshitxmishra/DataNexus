import React, { useEffect, useRef, useState, useMemo } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
// Vite native URL worker import
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.js?url';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Eye,
  EyeOff,
  Crosshair,
  AlertCircle,
  CheckCircle2,
  Layers,
  FileText
} from 'lucide-react';
import { DocumentEvidenceCoordinates, FieldCoordinateItem, LineItemCoordinateItem } from '../types';
import { api } from '../services/api';

// Set worker source using bundled worker asset
if (typeof window !== 'undefined') {
  pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl || `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`;
}

interface PDFVisualEvidenceViewerProps {
  documentId: string;
  filename: string;
  fileType: string;
  selectedFieldId: string | null;
  targetPage?: number | null;
  coordinatesData: DocumentEvidenceCoordinates | null;
  onSelectField?: (fieldId: string) => void;
}

export const PDFVisualEvidenceViewer: React.FC<PDFVisualEvidenceViewerProps> = ({
  documentId,
  filename,
  fileType,
  selectedFieldId,
  targetPage,
  coordinatesData,
  onSelectField,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.15);
  const [rendering, setRendering] = useState<boolean>(false);
  const [showHighlights, setShowHighlights] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeHighlightInfo, setActiveHighlightInfo] = useState<string | null>(null);

  const isPdf = fileType === 'application/pdf' || filename.toLowerCase().endsWith('.pdf');

  // Load PDF Document
  useEffect(() => {
    if (!isPdf) return;

    let isMounted = true;
    const downloadUrl = api.getDocumentDownloadUrl(documentId);

    const loadPdf = async () => {
      try {
        setLoadError(null);
        const loadingTask = pdfjsLib.getDocument({
          url: downloadUrl,
          withCredentials: false
        });
        const doc = await loadingTask.promise;
        if (isMounted) {
          setPdfDoc(doc);
          setTotalPages(doc.numPages);
          setCurrentPage(targetPage || 1);
        }
      } catch (err: any) {
        if (isMounted) {
          console.error('Failed to load PDF via PDF.js:', err);
          setLoadError(err.message || 'Unable to render PDF binary in visual canvas.');
        }
      }
    };

    loadPdf();

    return () => {
      isMounted = false;
    };
  }, [documentId, isPdf]);

  // Handle external page navigation when targetPage changes
  useEffect(() => {
    if (targetPage && targetPage >= 1 && targetPage <= totalPages) {
      setCurrentPage(targetPage);
    }
  }, [targetPage, totalPages]);

  // Render current page onto HTML5 canvas
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let renderTask: any = null;
    let isCancelled = false;

    const renderPage = async () => {
      try {
        setRendering(true);
        const page = await pdfDoc.getPage(currentPage);
        if (isCancelled) return;

        const viewport = page.getViewport({ scale });
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        canvas.width = viewport.width;
        canvas.height = viewport.height;

        const renderContext = {
          canvasContext: ctx,
          viewport: viewport,
        };

        renderTask = page.render(renderContext);
        await renderTask.promise;
      } catch (err: any) {
        if (!isCancelled && err.name !== 'RenderingCancelledException') {
          console.error('Error rendering page:', err);
        }
      } finally {
        if (!isCancelled) setRendering(false);
      }
    };

    renderPage();

    return () => {
      isCancelled = true;
      if (renderTask) {
        renderTask.cancel();
      }
    };
  }, [pdfDoc, currentPage, scale]);

  // Collect page highlights for current page
  const pageHighlights = useMemo(() => {
    if (!coordinatesData || !showHighlights) return [];

    const highlights: Array<{
      id: string;
      label: string;
      value: string;
      color: string;
      isFocused: boolean;
      norm_left_pct: number;
      norm_top_pct: number;
      norm_width_pct: number;
      norm_height_pct: number;
    }> = [];

    // 1. Extracted fields on current page
    Object.values(coordinatesData.field_coordinates || {}).forEach((item: FieldCoordinateItem) => {
      if (item.page_number === currentPage && item.has_coordinates && item.bounding_box) {
        const isFocused = item.field_id === selectedFieldId;
        const color = getFieldColor(item.field_name);
        highlights.push({
          id: item.field_id,
          label: item.field_name.replace('_', ' '),
          value: item.field_value,
          color,
          isFocused,
          norm_left_pct: item.bounding_box.norm_left_pct,
          norm_top_pct: item.bounding_box.norm_top_pct,
          norm_width_pct: item.bounding_box.norm_width_pct,
          norm_height_pct: item.bounding_box.norm_height_pct,
        });
      }
    });

    // 2. Line items on current page
    (coordinatesData.line_item_coordinates || []).forEach((item: LineItemCoordinateItem) => {
      if (item.page_number === currentPage && item.has_coordinates && item.bounding_box) {
        highlights.push({
          id: item.line_id,
          label: `Line #${item.line_number}`,
          value: `${item.description} ($${item.amount.toFixed(2)})`,
          color: 'blue',
          isFocused: false,
          norm_left_pct: item.bounding_box.norm_left_pct,
          norm_top_pct: item.bounding_box.norm_top_pct,
          norm_width_pct: item.bounding_box.norm_width_pct,
          norm_height_pct: item.bounding_box.norm_height_pct,
        });
      }
    });

    return highlights;
  }, [coordinatesData, currentPage, showHighlights, selectedFieldId]);

  // Color mapping helper
  function getFieldColor(fieldName: string): string {
    switch (fieldName) {
      case 'invoice_number':
        return 'cyan';
      case 'vendor_name':
        return 'purple';
      case 'total_amount':
        return 'emerald';
      case 'invoice_date':
      case 'due_date':
        return 'amber';
      case 'subtotal':
      case 'tax_amount':
        return 'indigo';
      default:
        return 'emerald';
    }
  }

  // Non-PDF Fallback View
  if (!isPdf) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-3 font-mono text-xs">
        <div className="flex items-center space-x-2 text-slate-300 font-semibold">
          <FileText className="w-4 h-4 text-brand-400" />
          <span>Non-PDF Document Viewer</span>
        </div>
        <p className="text-slate-400 font-sans leading-relaxed">
          The visual PDF coordinate overlay requires an original PDF binary. This file is registered as{' '}
          <strong className="text-white">{fileType}</strong>. All character offsets, extracted fields, and
          lineage anchors remain fully verifiable in the Field Provenance Inspector panel.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden flex flex-col font-mono text-xs">
      {/* Viewer Navigation & Controls Toolbar */}
      <div className="p-3 bg-slate-950 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        {/* Page Switcher */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage <= 1 || rendering}
            className="p-1 rounded bg-slate-900 hover:bg-slate-800 disabled:opacity-40 border border-slate-800 text-slate-300 transition"
            title="Previous Page"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-slate-300 text-xs px-2">
            Page <strong className="text-white">{currentPage}</strong> of{' '}
            <strong className="text-slate-400">{totalPages}</strong>
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage >= totalPages || rendering}
            className="p-1 rounded bg-slate-900 hover:bg-slate-800 disabled:opacity-40 border border-slate-800 text-slate-300 transition"
            title="Next Page"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom & Fit Controls */}
        <div className="flex items-center space-x-1.5">
          <button
            onClick={() => setScale((s) => Math.max(0.75, s - 0.15))}
            className="p-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-slate-400 text-[11px] px-1 w-12 text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            onClick={() => setScale((s) => Math.min(2.0, s + 0.15))}
            className="p-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setScale(1.15)}
            className="px-2 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 text-[11px] transition"
            title="Reset Scale"
          >
            Fit
          </button>
        </div>

        {/* Highlights Toggle & Active Focus Badge */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowHighlights(!showHighlights)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded border text-xs transition ${
              showHighlights
                ? 'bg-brand-600/20 text-brand-300 border-brand-500/40'
                : 'bg-slate-900 text-slate-400 border-slate-800'
            }`}
          >
            {showHighlights ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>Bounding Boxes ({pageHighlights.length})</span>
          </button>

          {coordinatesData && (
            <span className="flex items-center space-x-1 text-[10px] text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded">
              <CheckCircle2 className="w-3 h-3" />
              <span>Native Stream Coords</span>
            </span>
          )}
        </div>
      </div>

      {/* Active Focus Notification Bar */}
      {selectedFieldId && (
        <div className="bg-brand-950/40 border-b border-brand-500/30 px-4 py-1.5 flex items-center justify-between text-[11px] text-brand-300">
          <div className="flex items-center space-x-1.5">
            <Crosshair className="w-3.5 h-3.5 text-brand-400 animate-pulse" />
            <span>Target Evidence Focused on Page {currentPage}</span>
          </div>
          {pageHighlights.some((h) => h.isFocused) ? (
            <span className="text-emerald-400 text-[10px]">● Box Highlighted on Canvas</span>
          ) : (
            <span className="text-amber-400 text-[10px]">
              Coordinates not on Page {currentPage} or unreferenced
            </span>
          )}
        </div>
      )}

      {/* Canvas & Overlay Viewport Container */}
      <div
        ref={containerRef}
        className="p-6 bg-slate-950/80 overflow-auto flex justify-center items-start min-h-[550px] max-h-[750px] relative select-none"
      >
        {loadError ? (
          <div className="p-8 text-center text-rose-400 space-y-2 max-w-md">
            <AlertCircle className="w-8 h-8 mx-auto text-rose-500" />
            <div className="font-semibold text-sm">Failed to Load Visual PDF Canvas</div>
            <p className="text-xs text-slate-400 font-sans">{loadError}</p>
          </div>
        ) : (
          <div className="relative inline-block shadow-2xl rounded border border-slate-800 bg-white">
            {/* Native PDF.js HTML5 Canvas */}
            <canvas ref={canvasRef} className="block max-w-none" />

            {/* Visual Bounding Box Overlay Layer */}
            {showHighlights && (
              <div className="absolute inset-0 pointer-events-none">
                {pageHighlights.map((hl) => {
                  const borderClasses = hl.isFocused
                    ? 'border-2 border-brand-400 bg-brand-400/25 ring-4 ring-brand-500/40 shadow-lg'
                    : hl.color === 'cyan'
                    ? 'border border-cyan-400/80 bg-cyan-400/15 hover:bg-cyan-400/25'
                    : hl.color === 'purple'
                    ? 'border border-purple-400/80 bg-purple-400/15 hover:bg-purple-400/25'
                    : hl.color === 'emerald'
                    ? 'border border-emerald-400/80 bg-emerald-400/15 hover:bg-emerald-400/25'
                    : hl.color === 'amber'
                    ? 'border border-amber-400/80 bg-amber-400/15 hover:bg-amber-400/25'
                    : 'border border-blue-400/80 bg-blue-400/15 hover:bg-blue-400/25';

                  return (
                    <div
                      key={hl.id}
                      onClick={() => onSelectField && onSelectField(hl.id)}
                      onMouseEnter={() => setActiveHighlightInfo(`${hl.label}: ${hl.value}`)}
                      onMouseLeave={() => setActiveHighlightInfo(null)}
                      className={`absolute rounded pointer-events-auto cursor-pointer transition-all duration-150 ${borderClasses}`}
                      style={{
                        left: `${hl.norm_left_pct}%`,
                        top: `${hl.norm_top_pct}%`,
                        width: `${hl.norm_width_pct}%`,
                        height: `${hl.norm_height_pct}%`,
                      }}
                      title={`${hl.label}: ${hl.value}`}
                    >
                      {/* Floating Mini Tag */}
                      <span
                        className={`absolute -top-3.5 left-0 px-1 py-0.2 rounded text-[8px] font-bold uppercase tracking-wider whitespace-nowrap shadow-sm ${
                          hl.isFocused
                            ? 'bg-brand-500 text-white'
                            : 'bg-slate-900/90 text-slate-200 border border-slate-700'
                        }`}
                      >
                        {hl.label}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer Info & Hover Tooltip */}
      <div className="p-2.5 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
        <div className="flex items-center space-x-2">
          <Layers className="w-3.5 h-3.5 text-slate-500" />
          <span>
            {activeHighlightInfo ? (
              <strong className="text-white">{activeHighlightInfo}</strong>
            ) : (
              'Click any highlight box to inspect field provenance details'
            )}
          </span>
        </div>
        <div className="flex items-center space-x-3 text-[10px]">
          <span className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded bg-cyan-400/40 border border-cyan-400"></span>
            <span>Invoice #</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded bg-purple-400/40 border border-purple-400"></span>
            <span>Vendor</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded bg-emerald-400/40 border border-emerald-400"></span>
            <span>Amounts</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded bg-amber-400/40 border border-amber-400"></span>
            <span>Dates</span>
          </span>
        </div>
      </div>
    </div>
  );
};

