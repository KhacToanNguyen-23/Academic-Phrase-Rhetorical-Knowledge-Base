import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, unwrap } from "@/features/slr-import/api/client";
import { Badge, Card } from "@/shared/ui";
import { vocabularyClient } from "../api/client";

type ImportResult = {
  source_kind: string;
  rows_read: number;
  inserted: number;
  updated: number;
  skipped: number;
  warnings: string[];
};

export function VocabularyImportCard({ onClose }: { onClose?: () => void }) {
  const { client: authClient } = useAuth();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [results, setResults] = useState<ImportResult[]>([]);
  const [message, setMessage] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const allowed = authClient?.role === "curator" || authClient?.role === "admin";

  const upload = useMutation({
    mutationFn: async () => {
      const api = vocabularyClient();
      const imported: ImportResult[] = [];
      for (const file of files) {
        const form = new FormData();
        form.append("file", file);
        const response = await api.POST("/v1/admin/vocabulary/imports", {
          body: { file: file.name } as never,
          bodySerializer: () => form,
        });
        imported.push(unwrap(response) as ImportResult);
        setResults([...imported]);
      }
      return imported;
    },
    onSuccess: (imported) => {
      setMessage(`Successfully imported ${imported.length} file(s).`);
      setFiles([]);
      void queryClient.invalidateQueries({ queryKey: ["vocabulary-lemmas"] });
      void queryClient.invalidateQueries({ queryKey: ["vocabulary-letters"] });
      void queryClient.invalidateQueries({ queryKey: ["vocabulary-families"] });
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.message : error.message || "Import failed."),
  });

  if (!allowed) return null;

  const handleFileSelect = (newFiles: FileList | null) => {
    if (!newFiles) return;
    const xlsxFiles = Array.from(newFiles).filter(
      (f) => f.name.endsWith(".xlsx") || f.type.includes("spreadsheet") || f.type.includes("excel"),
    );
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const additions = xlsxFiles.filter((f) => !existingNames.has(f.name));
      return [...prev, ...additions];
    });
    setMessage("");
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <Card
      title="Import Academic Vocabulary List"
      aside={
        <div className="vocab-import-head-actions">
          <Badge tone="info">Curator Tool</Badge>
          {onClose && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onClose}
              aria-label="Close import panel"
            >
              ✕ Close
            </button>
          )}
        </div>
      }
    >
      <div className="vocab-import-container">
        <div
          className={`vocab-dropzone ${isDragging ? "is-dragover" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          aria-label="Upload Excel files"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            multiple
            className="sr-only"
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              handleFileSelect(e.target.files);
              e.target.value = "";
            }}
          />
          <div className="vocab-dropzone-icon" aria-hidden>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <div className="vocab-dropzone-text">
            <strong>Choose files or drag & drop</strong>
            <span className="caption">Accepts Gardner & Davies AVL spreadsheet formats (.xlsx)</span>
          </div>
        </div>

        {files.length > 0 && (
          <div className="vocab-selected-files">
            <span className="vocab-selected-label">Selected spreadsheets ({files.length}):</span>
            <ul className="vocab-file-chips">
              {files.map((file, idx) => (
                <li key={`${file.name}-${idx}`} className="vocab-file-chip">
                  <span className="vocab-file-name" title={file.name}>{file.name}</span>
                  <span className="vocab-file-size">{(file.size / 1024).toFixed(0)} KB</span>
                  <button
                    type="button"
                    className="vocab-file-remove"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(idx);
                    }}
                    aria-label={`Remove ${file.name}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="vocab-import-actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={files.length === 0 || upload.isPending}
            onClick={() => upload.mutate()}
          >
            {upload.isPending ? "Importing data..." : `Import ${files.length ? `${files.length} file(s)` : ""}`}
          </button>
          {files.length > 0 && !upload.isPending && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setFiles([]);
                setMessage("");
              }}
            >
              Clear
            </button>
          )}
        </div>

        {message && (
          <div className={`notice ${upload.isError ? "notice-warn" : "notice-ok"}`} role="status">
            {message}
          </div>
        )}

        {results.length > 0 && (
          <div className="vocab-import-results">
            <h3 className="vocab-results-heading">Import Summary</h3>
            <div className="vocab-results-grid">
              {results.map((result, idx) => (
                <div key={`${result.source_kind}-${idx}`} className="vocab-result-item">
                  <div className="vocab-result-head">
                    <Badge tone="ok">{result.source_kind}</Badge>
                    <span className="caption">{result.rows_read} rows read</span>
                  </div>
                  <div className="vocab-result-metrics">
                    <div className="vocab-metric">
                      <span className="vocab-metric-num">{result.inserted}</span>
                      <span className="vocab-metric-label">Inserted</span>
                    </div>
                    <div className="vocab-metric">
                      <span className="vocab-metric-num">{result.updated}</span>
                      <span className="vocab-metric-label">Updated</span>
                    </div>
                    <div className="vocab-metric">
                      <span className="vocab-metric-num">{result.skipped}</span>
                      <span className="vocab-metric-label">Skipped</span>
                    </div>
                  </div>
                  {result.warnings.length > 0 && (
                    <details className="vocab-result-warnings">
                      <summary>{result.warnings.length} warning(s)</summary>
                      <ul>
                        {result.warnings.map((w, wIdx) => (
                          <li key={wIdx}>{w}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
