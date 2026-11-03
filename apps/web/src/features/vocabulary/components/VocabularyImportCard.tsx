import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRef, useState, type ChangeEvent, type DragEvent } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/features/auth/AuthProvider"
import { ApiError, unwrap } from "@/features/slr-import/api/client"
import { vocabularyClient } from "../api/client"

type ImportResult = { source_kind: string; rows_read: number; inserted: number; updated: number; skipped: number; warnings: string[] }

export function VocabularyImportCard({ onClose }: { onClose?: () => void }) {
  const { client: authClient } = useAuth()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [results, setResults] = useState<ImportResult[]>([])
  const [message, setMessage] = useState("")
  const [isDragging, setIsDragging] = useState(false)
  const allowed = authClient?.role === "curator" || authClient?.role === "admin"

  const upload = useMutation({
    mutationFn: async () => {
      const api = vocabularyClient()
      const imported: ImportResult[] = []
      for (const file of files) {
        const form = new FormData()
        form.append("file", file)
        const response = await api.POST("/v1/admin/vocabulary/imports", { body: { file: file.name } as never, bodySerializer: () => form })
        imported.push(unwrap(response) as ImportResult)
        setResults([...imported])
      }
      return imported
    },
    onSuccess: (imported) => {
      setMessage(`Successfully imported ${imported.length} file(s).`)
      setFiles([])
      void queryClient.invalidateQueries({ queryKey: ["vocabulary-lemmas"] })
      void queryClient.invalidateQueries({ queryKey: ["vocabulary-letters"] })
      void queryClient.invalidateQueries({ queryKey: ["vocabulary-families"] })
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.message : error.message || "Import failed."),
  })

  if (!allowed) return null
  const handleFileSelect = (newFiles: FileList | null) => {
    if (!newFiles) return
    const xlsxFiles = Array.from(newFiles).filter((file) => file.name.endsWith(".xlsx") || file.type.includes("spreadsheet") || file.type.includes("excel"))
    setFiles((previous) => { const existing = new Set(previous.map((file) => file.name)); return [...previous, ...xlsxFiles.filter((file) => !existing.has(file.name))] })
    setMessage("")
  }
  const handleDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setIsDragging(false); handleFileSelect(event.dataTransfer.files) }

  return <Card><CardHeader className="flex-row items-center justify-between"><CardTitle>Import academic vocabulary</CardTitle><div className="flex items-center gap-2"><Badge variant="secondary">Curator tool</Badge>{onClose ? <Button variant="ghost" size="sm" onClick={onClose}>Close</Button> : null}</div></CardHeader><CardContent className="flex flex-col gap-4">
    <div className={`flex items-center justify-between gap-4 rounded-[var(--radius)] border border-dashed p-6 ${isDragging ? "bg-muted" : "bg-card"}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}><input id="vocabulary-files" ref={fileInputRef} type="file" accept=".xlsx" multiple className="sr-only" onChange={(event: ChangeEvent<HTMLInputElement>) => { handleFileSelect(event.target.files); event.target.value = "" }} /><label htmlFor="vocabulary-files" className="cursor-pointer"><p className="font-medium">Choose spreadsheets or drag them here</p><p className="text-sm text-muted-foreground">Accepts .xlsx files in the supported vocabulary formats.</p></label><Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>Choose files</Button></div>
    {files.length > 0 ? <div className="flex flex-col gap-2"><p className="text-sm font-medium">Selected spreadsheets ({files.length})</p><ul className="flex flex-col gap-2">{files.map((file, index) => <li key={`${file.name}-${index}`} className="flex items-center justify-between rounded-[var(--radius)] border border-border px-3 py-2 text-sm"><span>{file.name} <span className="text-muted-foreground">({(file.size / 1024).toFixed(0)} KB)</span></span><Button variant="ghost" size="sm" aria-label={`Remove ${file.name}`} onClick={() => setFiles((previous) => previous.filter((_, fileIndex) => fileIndex !== index))}>Remove</Button></li>)}</ul></div> : null}
    <div className="flex items-center gap-2"><Button disabled={files.length === 0 || upload.isPending} onClick={() => upload.mutate()}>{upload.isPending ? "Importing data…" : `Import${files.length ? ` ${files.length} file(s)` : ""}`}</Button>{files.length > 0 && !upload.isPending ? <Button variant="outline" onClick={() => { setFiles([]); setMessage("") }}>Clear</Button> : null}</div>
    {message ? <Alert variant={upload.isError ? "destructive" : "default"}><AlertTitle>{upload.isError ? "Import failed" : "Import complete"}</AlertTitle><AlertDescription>{message}</AlertDescription></Alert> : null}
    {results.length > 0 ? <div className="flex flex-col gap-3"><h3 className="font-medium">Import summary</h3>{results.map((result, index) => <div key={`${result.source_kind}-${index}`} className="rounded-[var(--radius)] border border-border p-3"><div className="flex items-center justify-between"><Badge variant="success">{result.source_kind}</Badge><span className="text-sm text-muted-foreground">{result.rows_read} rows read</span></div><dl className="mt-3 grid grid-cols-3 gap-3 text-sm"><div><dt className="text-muted-foreground">Inserted</dt><dd className="font-medium tabular-nums">{result.inserted}</dd></div><div><dt className="text-muted-foreground">Updated</dt><dd className="font-medium tabular-nums">{result.updated}</dd></div><div><dt className="text-muted-foreground">Skipped</dt><dd className="font-medium tabular-nums">{result.skipped}</dd></div></dl>{result.warnings.length > 0 ? <details className="mt-3 text-sm"><summary>{result.warnings.length} warning(s)</summary><ul className="mt-2 flex list-disc flex-col gap-1 pl-5">{result.warnings.map((warning, warningIndex) => <li key={warningIndex}>{warning}</li>)}</ul></details> : null}</div>)}</div> : null}
  </CardContent></Card>
}
