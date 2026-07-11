/**
 * ImportExport — PLUM data import / export page.
 *
 * Route: /plum/import-export
 *
 * Layout: p-8 space-y-6 (standard page wrapper)
 *
 * Sections:
 *   - PlumNav tab strip
 *   - Page heading "Import / Export" + subtitle
 *   - Export Card: two outline buttons (JSON + Excel) that stream a file download
 *   - Import Card: 3-step inline flow (upload → preview → committed)
 *     Step 1: dashed dropzone + hidden file input, "Upload and Preview" button
 *     Step 2: summary banner + optional error table + "Confirm Import" / "Back to Upload"
 *     Step 3: success state with counts + "Import Another File"
 *
 * API endpoints (Plan 03):
 *   GET  /api/v1/plum/export/json   → blob download
 *   GET  /api/v1/plum/export/excel  → blob download
 *   POST /api/v1/plum/import/preview → ImportPreviewResponse
 *   POST /api/v1/plum/import/commit  → ImportCommitResponse
 *
 * Threat mitigations:
 *   T-06-22: export authenticated (apiClient carries auth header)
 *   T-06-23: backend rejects >10 MB; UI surfaces via getApiErrorMessage
 *   T-06-24: preview-before-commit enforced; Confirm Import disabled on errors
 */

import { useState, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, FileSpreadsheet, Upload, CheckCircle, Loader2, X } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { apiClient } from '@/api/client'
import { PlumNav } from './components/PlumNav'

// ─── Types ───────────────────────────────────────────────────────────────────

interface ImportRowError {
  row: number | string
  field: string
  message: string
}

interface ImportPreviewResponse {
  new_count: number
  updated_count: number
  errors: ImportRowError[]
}

interface ImportCommitResponse {
  inserted: number
  updated: number
}

// ─── API error helper ─────────────────────────────────────────────────────────
function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => {
          const loc = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : undefined
          const field = typeof loc === 'string' ? loc : undefined
          const msg = typeof d?.msg === 'string' ? d.msg : 'invalid value'
          return field ? `${field}: ${msg}` : msg
        })
        .filter(Boolean)
      if (msgs.length) return msgs.join('; ')
    }
  }
  return fallback
}

// ─── Blob download helper ─────────────────────────────────────────────────────

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ImportExport() {
  // ── Import step state ──
  const [importStep, setImportStep] = useState<'upload' | 'preview' | 'committed'>('upload')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null)
  const [committedData, setCommittedData] = useState<ImportCommitResponse | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  // ── Export mutations ──
  const exportJsonMutation = useMutation<void, Error>({
    mutationFn: async () => {
      const response = await apiClient.get<Blob>('/api/v1/plum/export/json', {
        responseType: 'blob',
      })
      triggerBlobDownload(response.data, 'plum_export.json')
    },
    onSuccess: () => {
      toast('Export started — your download will begin shortly.')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Export failed. Check your connection and try again.'))
    },
  })

  const exportExcelMutation = useMutation<void, Error>({
    mutationFn: async () => {
      const response = await apiClient.get<Blob>('/api/v1/plum/export/excel', {
        responseType: 'blob',
      })
      triggerBlobDownload(response.data, 'plum_export.xlsx')
    },
    onSuccess: () => {
      toast('Export started — your download will begin shortly.')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Export failed. Check your connection and try again.'))
    },
  })

  // ── Upload and preview mutation ──
  const uploadPreviewMutation = useMutation<ImportPreviewResponse, Error, File>({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const response = await apiClient.post<ImportPreviewResponse>(
        '/api/v1/plum/import/preview',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      return response.data
    },
    onSuccess: (data) => {
      setPreviewData(data)
      setImportStep('preview')
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Upload failed. Check your connection and try again.'))
    },
  })

  // ── Commit import mutation ──
  const commitImportMutation = useMutation<ImportCommitResponse, Error, File>({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const response = await apiClient.post<ImportCommitResponse>(
        '/api/v1/plum/import/commit',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      return response.data
    },
    onSuccess: (data) => {
      setCommittedData(data)
      setImportStep('committed')
      toast(`Import complete. ${data.inserted} inserted, ${data.updated} updated.`)
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
    },
    onError: (err) => {
      toast.error(
        getApiErrorMessage(err, 'Import failed. No changes were made. Please try again.'),
      )
    },
  })

  // ── Handlers ──

  function acceptFile(file: File | null | undefined) {
    if (!file) return
    const name = file.name.toLowerCase()
    if (!name.endsWith('.json') && !name.endsWith('.xlsx')) {
      toast.error('Unsupported file type. Choose a .json or .xlsx file.')
      return
    }
    setSelectedFile(file)
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    acceptFile(e.target.files?.[0])
    // Reset input value so the same file can be re-selected after clearing
    e.target.value = ''
  }

  function handleBrowseClick() {
    fileInputRef.current?.click()
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(true)
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(false)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragging(false)
    acceptFile(e.dataTransfer.files?.[0])
  }

  function handleClearFile() {
    setSelectedFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function handleUploadAndPreview() {
    if (!selectedFile) return
    uploadPreviewMutation.mutate(selectedFile)
  }

  function handleConfirmImport() {
    if (!selectedFile) return
    commitImportMutation.mutate(selectedFile)
  }

  function handleBackToUpload() {
    setImportStep('upload')
    setPreviewData(null)
  }

  function resetImport() {
    setImportStep('upload')
    setSelectedFile(null)
    setPreviewData(null)
    setCommittedData(null)
  }

  // ── Derived values ──
  const hasErrors = (previewData?.errors.length ?? 0) > 0
  const errorCount = previewData?.errors.length ?? 0

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      <PlumNav />

      {/* Page heading */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Import / Export</h1>
        <p className="text-base font-normal text-muted-foreground">Move data in and out of PLUM.</p>
      </div>

      {/* ── Export Card ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">Export</h2>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 max-w-xs">
            <Button
              variant="outline"
              onClick={() => exportJsonMutation.mutate()}
              disabled={exportJsonMutation.isPending || exportExcelMutation.isPending}
            >
              {exportJsonMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" aria-hidden="true" />
                  Exporting…
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 mr-2" aria-hidden="true" />
                  Export as JSON
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={() => exportExcelMutation.mutate()}
              disabled={exportJsonMutation.isPending || exportExcelMutation.isPending}
            >
              {exportExcelMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" aria-hidden="true" />
                  Exporting…
                </>
              ) : (
                <>
                  <FileSpreadsheet className="h-4 w-4 mr-2" aria-hidden="true" />
                  Export as Excel
                </>
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            JSON export is the full lossless dataset. Excel export is a human-friendly
            multi-sheet workbook (Parts, BOMs, AVL).
          </p>
        </CardContent>
      </Card>

      {/* ── Import Card ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-foreground">Import</h2>
          </div>
        </CardHeader>
        <CardContent>
          {/* ── Step 1: Upload ── */}
          {importStep === 'upload' && (
            <div className="space-y-4">
              {/* Dropzone */}
              <div
                role="button"
                tabIndex={0}
                onClick={handleBrowseClick}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleBrowseClick()
                  }
                }}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-md p-8 text-center cursor-pointer transition-colors ${
                  isDragging ? 'border-primary bg-muted/50' : 'border-border hover:border-muted-foreground'
                }`}
              >
                <Upload className="h-8 w-8 text-muted-foreground mx-auto mb-2" aria-hidden="true" />
                <p className="text-sm text-foreground font-medium">Drop a JSON or Excel file here</p>
                <p className="text-xs text-muted-foreground mt-1">or</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={(e) => {
                    e.stopPropagation()
                    handleBrowseClick()
                  }}
                >
                  Choose File
                </Button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,.xlsx"
                className="sr-only"
                onChange={handleFileChange}
                aria-label="Choose a JSON or Excel file to import"
              />
              <p className="text-xs text-muted-foreground">Accepted: .json, .xlsx</p>

              {/* Selected file display */}
              {selectedFile && (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground truncate">
                    {selectedFile.name}
                  </span>
                  <button
                    type="button"
                    onClick={handleClearFile}
                    className="text-muted-foreground hover:text-foreground flex-none"
                    aria-label="Clear selected file"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              )}

              <Button
                variant="default"
                onClick={handleUploadAndPreview}
                disabled={!selectedFile || uploadPreviewMutation.isPending}
              >
                {uploadPreviewMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" aria-hidden="true" />
                    Uploading…
                  </>
                ) : (
                  'Upload and Preview'
                )}
              </Button>
            </div>
          )}

          {/* ── Step 2: Preview ── */}
          {importStep === 'preview' && previewData && (
            <div className="space-y-4">
              {/* Summary banner */}
              <div className="rounded-md border border-border p-4 space-y-1 text-sm">
                <p>
                  <span className="font-semibold">{previewData.new_count} new</span> records will be inserted
                </p>
                <p>
                  <span className="font-semibold">{previewData.updated_count} existing</span> records will be updated
                </p>
                {hasErrors && (
                  <p className="text-destructive font-semibold">
                    {errorCount} errors must be resolved before import
                  </p>
                )}
              </div>

              {/* Error table */}
              {hasErrors && (
                <div className="max-h-64 overflow-y-auto rounded-md border border-border">
                  <Table aria-label="Import validation errors">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Row</TableHead>
                        <TableHead>Field</TableHead>
                        <TableHead>Error Message</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {previewData.errors.map((err, idx) => (
                        <TableRow key={idx}>
                          <TableCell className="font-mono text-sm">{err.row}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">{err.field}</TableCell>
                          <TableCell className="text-sm text-foreground">{err.message}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Block-commit note when errors exist */}
              {hasErrors && (
                <p className="text-xs text-destructive">
                  Resolve all errors before importing. Correct the source file and upload again.
                </p>
              )}

              {/* Action buttons */}
              <div className="flex gap-2">
                <Button
                  variant="default"
                  onClick={handleConfirmImport}
                  disabled={hasErrors || commitImportMutation.isPending}
                >
                  {commitImportMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" aria-hidden="true" />
                      Importing…
                    </>
                  ) : (
                    'Confirm Import'
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleBackToUpload}
                  disabled={commitImportMutation.isPending}
                >
                  Back to Upload
                </Button>
              </div>
            </div>
          )}

          {/* ── Step 3: Committed ── */}
          {importStep === 'committed' && committedData && (
            <div className="text-center py-8 space-y-2">
              <CheckCircle className="h-8 w-8 text-green-600 mx-auto" aria-hidden="true" />
              <p className="text-base font-semibold text-foreground">Import complete</p>
              <p className="text-sm text-muted-foreground">
                {committedData.inserted} inserted, {committedData.updated} updated. No records were deleted.
              </p>
              <Button variant="outline" size="sm" className="mt-2" onClick={resetImport}>
                Import Another File
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
