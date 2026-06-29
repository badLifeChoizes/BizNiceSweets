/**
 * PartsList screen — PLUM parts master data list (/plum/parts).
 *
 * Layout: p-8 space-y-6 (matches Vendors/Users/GLAccounts pattern).
 *
 * Toolbar:
 *   - Search Input (server-side, debounced 300ms via ?q= param)
 *   - Status Select (filters by current revision status via ?status=)
 *   - Show Archived Switch (wires to ?include_archived= param, D-11)
 *   - Create Part Button (variant="default" — only accent element, ml-auto)
 *
 * Table columns: Part Number | Description | Tags | Current Revision | Status | Actions
 *
 * Row click (not Actions cell) navigates to /plum/parts/:id (Part Detail).
 *
 * Row actions (DropdownMenu):
 *   - Edit    → opens PartSheet (edit mode)
 *   - Archive → opens ArchivePartDialog (active rows only)
 *   - Restore → direct PATCH {active:true} + toast (archived rows only, no confirmation)
 *
 * Query key: ['plum', 'parts', { q, status, includeArchived }]
 *
 * Accessibility: row aria-label, status badge uses color + text, icon aria-hidden.
 *
 * Threat mitigations:
 *   T-05-10: React JSX auto-escapes all interpolated values — no dangerouslySetInnerHTML.
 *   T-05-11: include_archived defaults false; archived parts hidden by default.
 */

import { useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MoreHorizontal, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { apiClient } from '@/api/client'
import { PlumNav } from './components/PlumNav'
import { PartSheet } from './components/PartSheet'
import { ArchivePartDialog } from './components/ArchivePartDialog'
import type { PartRead } from './components/PartSheet'

// ─── Status badge color map (UI-SPEC lines 89–95) ────────────────────────────
// Color AND text together — never color alone (accessibility requirement).

const STATUS_BADGE_CLASSES: Record<string, string> = {
  draft:     'bg-gray-100 text-gray-600',
  in_review: 'bg-yellow-50 text-yellow-700',
  released:  'bg-green-50 text-green-600',
  obsolete:  'bg-gray-100 text-gray-400',
}

function RevisionStatusBadge({ status }: { status: string }) {
  const classes = STATUS_BADGE_CLASSES[status] ?? 'bg-gray-100 text-gray-500'
  const label = status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${classes}`}
    >
      {label}
    </span>
  )
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchParts(q: string, status: string, includeArchived: boolean): Promise<PartRead[]> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (status) params.set('status', status)
  if (includeArchived) params.set('include_archived', 'true')
  return apiClient
    .get<PartRead[]>(`/api/v1/plum/parts?${params.toString()}`)
    .then((r) => r.data)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function PartsList() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // ── Search (debounced, server-side) ──
  const [searchValue, setSearchValue] = useState('')
  const [searchFilter, setSearchFilter] = useState('')
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    setSearchValue(v)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => setSearchFilter(v), 300)
  }, [])

  // ── Status filter ──
  const [statusFilter, setStatusFilter] = useState('')

  // ── Show archived toggle ──
  const [includeArchived, setIncludeArchived] = useState(false)

  // ── Sheet state ──
  const [sheetOpen, setSheetOpen] = useState(false)
  const [sheetMode, setSheetMode] = useState<'create' | 'edit'>('create')
  const [sheetPart, setSheetPart] = useState<PartRead | null>(null)

  // ── Archive dialog state ──
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [archivePart, setArchivePart] = useState<PartRead | null>(null)

  // ── Data ──
  const { data: parts = [], isLoading, isError } = useQuery<PartRead[], Error>({
    queryKey: ['plum', 'parts', { q: searchFilter, status: statusFilter, includeArchived }],
    queryFn: () => fetchParts(searchFilter, statusFilter, includeArchived),
  })

  // ── Restore mutation ──
  const restoreMutation = useMutation<PartRead, Error, string>({
    mutationFn: (partId) =>
      apiClient
        .patch<PartRead>(`/api/v1/plum/parts/${partId}`, { active: true })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
      toast('Part restored.')
    },
    onError: () => {
      toast.error('Failed to restore part. Please try again.')
    },
  })

  // ── Handlers ──
  function openCreateSheet() {
    setSheetMode('create')
    setSheetPart(null)
    setSheetOpen(true)
  }

  function openEditSheet(part: PartRead) {
    setSheetMode('edit')
    setSheetPart(part)
    setSheetOpen(true)
  }

  function openArchiveDialog(part: PartRead) {
    setArchivePart(part)
    setArchiveOpen(true)
  }

  function handleRestore(part: PartRead) {
    restoreMutation.mutate(part.id)
  }

  const hasActiveFilter = Boolean(searchFilter || statusFilter)

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      <PlumNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Parts</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manage parts and their revision history.
        </p>
      </div>

      {/* Toolbar: Search + Status filter + Show archived + Create Part */}
      <div className="flex items-center gap-4">
        <Input
          placeholder="Search part number or description…"
          value={searchValue}
          onChange={handleSearchChange}
          className="max-w-xs"
          aria-label="Search parts"
        />
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[160px]" aria-label="Filter by status">
            <SelectValue placeholder="All Statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All Statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="in_review">In Review</SelectItem>
            <SelectItem value="released">Released</SelectItem>
            <SelectItem value="obsolete">Obsolete</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Switch
            id="parts-show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="parts-show-archived">Show archived</Label>
        </div>
        {/* "Create Part" is the ONLY accent/default button on this screen */}
        <Button variant="default" onClick={openCreateSheet} className="ml-auto">
          Create Part
        </Button>
      </div>

      {/* Parts table / loading / empty / error states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Could not load parts. Check your connection and try again.
          </p>
        </div>
      ) : parts.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          {hasActiveFilter ? (
            statusFilter && !searchFilter ? (
              <>
                <p className="text-base font-semibold text-foreground">No parts with that status</p>
                <p className="text-sm text-muted-foreground">
                  Try a different status filter or clear all filters.
                </p>
              </>
            ) : (
              <>
                <p className="text-base font-semibold text-foreground">No parts found</p>
                <p className="text-sm text-muted-foreground">
                  No parts match your search. Clear the filter or create a new part.
                </p>
              </>
            )
          ) : (
            <>
              <p className="text-base font-semibold text-foreground">No parts yet</p>
              <p className="text-sm text-muted-foreground">
                Create your first part to get started.
              </p>
            </>
          )}
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Part Number</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Tags</TableHead>
              <TableHead>Current Revision</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {parts.map((part) => (
              <TableRow
                key={part.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/plum/parts/${part.id}`)}
                aria-label={`View part ${part.part_number}`}
              >
                <TableCell className="font-medium">{part.part_number}</TableCell>
                <TableCell>—</TableCell>
                <TableCell>
                  {part.tags.length > 0 ? part.tags.join(', ') : '—'}
                </TableCell>
                <TableCell>
                  {part.current_revision_label ?? '—'}
                </TableCell>
                <TableCell>
                  {part.current_revision_status ? (
                    <RevisionStatusBadge status={part.current_revision_status} />
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Part actions for ${part.part_number}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation()
                          openEditSheet(part)
                        }}
                      >
                        Edit
                      </DropdownMenuItem>
                      {part.active ? (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            openArchiveDialog(part)
                          }}
                          className="text-destructive focus:text-destructive"
                        >
                          Archive
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            handleRestore(part)
                          }}
                        >
                          Restore
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── Create / Edit Sheet ──────────────────────────────────────────── */}
      <PartSheet
        open={sheetOpen}
        mode={sheetMode}
        part={sheetPart}
        onClose={() => setSheetOpen(false)}
      />

      {/* ─── Archive Confirmation Dialog ──────────────────────────────────── */}
      <ArchivePartDialog
        open={archiveOpen}
        part={archivePart}
        onClose={() => {
          setArchiveOpen(false)
          setArchivePart(null)
        }}
      />
    </div>
  )
}
