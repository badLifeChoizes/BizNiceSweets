/**
 * Vendors screen — SYERP vendor master data list (/syerp/vendors).
 *
 * Layout: p-8 space-y-6 (matches Users.tsx and AppShell pattern).
 *
 * Toolbar:
 *   - Search Input (server-side, debounced 300ms via ?q= param)
 *   - Show archived Switch (wires to include_archived query param)
 *   - Create Vendor Button (variant="default" — only accent element)
 *
 * Table columns: Name | Code | Contact | Country | Status | Actions
 *
 * Row actions (DropdownMenu):
 *   - Edit   → opens PartnerSheet (edit mode)
 *   - Archive → opens PartnerArchiveDialog (active rows only)
 *   - Restore → direct PATCH {active:true} + toast (archived rows only, no confirmation)
 *
 * Search: server-side via GET /api/v1/syerp/partners?role=vendor&q={term}&include_archived={bool}
 * Query key: ['syerp', 'partners', 'vendor', { q, includeArchived }]
 *
 * Accessibility: row aria-label, color+text status badge, decorative icon aria-hidden.
 */

import { useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MoreHorizontal, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
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
import { PartnerSheet } from './components/PartnerSheet'
import { PartnerArchiveDialog } from './components/PartnerArchiveDialog'
import type { PartnerRead } from './components/PartnerSheet'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchVendors(q: string, includeArchived: boolean): Promise<PartnerRead[]> {
  const params = new URLSearchParams({ role: 'vendor' })
  if (q) params.set('q', q)
  if (includeArchived) params.set('include_archived', 'true')
  return apiClient
    .get<PartnerRead[]>(`/api/v1/syerp/partners?${params.toString()}`)
    .then((r) => r.data)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function StatusBadge({ active }: { active: boolean }) {
  // Color AND text used together (never color alone) — accessibility requirement
  if (active) {
    return (
      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-green-50 text-green-600">
        Active
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-gray-100 text-gray-500">
      Archived
    </span>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Vendors() {
  const queryClient = useQueryClient()

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

  // ── Show archived toggle ──
  const [includeArchived, setIncludeArchived] = useState(false)

  // ── Sheet state ──
  const [sheetOpen, setSheetOpen] = useState(false)
  const [sheetMode, setSheetMode] = useState<'create' | 'edit'>('create')
  const [sheetPartner, setSheetPartner] = useState<PartnerRead | null>(null)

  // ── Archive dialog state ──
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [archivePartner, setArchivePartner] = useState<PartnerRead | null>(null)

  // ── Data ──
  const { data: vendors = [], isLoading, isError } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'vendor', { q: searchFilter, includeArchived }],
    queryFn: () => fetchVendors(searchFilter, includeArchived),
  })

  // ── Restore mutation ──
  const restoreMutation = useMutation<PartnerRead, Error, string>({
    mutationFn: (partnerId) =>
      apiClient
        .patch<PartnerRead>(`/api/v1/syerp/partners/${partnerId}`, { active: true })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'partners', 'vendor'] })
      toast('Vendor restored.')
    },
    onError: () => {
      toast.error('Failed to restore vendor. Please try again.')
    },
  })

  // ── Handlers ──
  function openCreateSheet() {
    setSheetMode('create')
    setSheetPartner(null)
    setSheetOpen(true)
  }

  function openEditSheet(partner: PartnerRead) {
    setSheetMode('edit')
    setSheetPartner(partner)
    setSheetOpen(true)
  }

  function openArchiveDialog(partner: PartnerRead) {
    setArchivePartner(partner)
    setArchiveOpen(true)
  }

  function handleRestore(partner: PartnerRead) {
    restoreMutation.mutate(partner.id)
  }

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Vendors</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manage vendor master data. Vendors can be linked to parts in PLUM.
        </p>
      </div>

      {/* Toolbar: Search + Show archived + Create Vendor */}
      <div className="flex items-center gap-4">
        <Input
          placeholder="Search vendors…"
          value={searchValue}
          onChange={handleSearchChange}
          className="max-w-xs"
          aria-label="Search vendors"
        />
        <div className="flex items-center gap-2">
          <Switch
            id="vendor-show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="vendor-show-archived">Show archived</Label>
        </div>
        {/* "Create Vendor" is the ONLY accent/default button on this screen */}
        <Button variant="default" onClick={openCreateSheet} className="ml-auto">
          Create Vendor
        </Button>
      </div>

      {/* Vendors table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load vendors. Check your connection and refresh the page.
          </p>
        </div>
      ) : vendors.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          {searchFilter ? (
            <>
              <p className="text-base font-semibold text-foreground">No vendors found</p>
              <p className="text-sm text-muted-foreground">
                No vendors match your search. Clear the filter or create a new vendor.
              </p>
            </>
          ) : (
            <>
              <p className="text-base font-semibold text-foreground">No vendors yet</p>
              <p className="text-sm text-muted-foreground">
                Add your first vendor to get started.
              </p>
            </>
          )}
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Country</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {vendors.map((vendor) => (
              <TableRow key={vendor.id} className="h-12">
                <TableCell className="font-medium">{vendor.name}</TableCell>
                <TableCell>{vendor.code}</TableCell>
                <TableCell>{vendor.contact_name ?? '—'}</TableCell>
                <TableCell>{vendor.addr_country ?? '—'}</TableCell>
                <TableCell>
                  <StatusBadge active={vendor.active} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Vendor actions for ${vendor.name}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditSheet(vendor)}>
                        Edit
                      </DropdownMenuItem>
                      {vendor.active ? (
                        <DropdownMenuItem
                          onClick={() => openArchiveDialog(vendor)}
                          className="text-destructive focus:text-destructive"
                        >
                          Archive
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => handleRestore(vendor)}>
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
      <PartnerSheet
        open={sheetOpen}
        mode={sheetMode}
        partner={sheetPartner}
        role="vendor"
        onClose={() => setSheetOpen(false)}
      />

      {/* ─── Archive Confirmation Dialog ──────────────────────────────────── */}
      <PartnerArchiveDialog
        open={archiveOpen}
        partner={archivePartner}
        role="vendor"
        onClose={() => {
          setArchiveOpen(false)
          setArchivePartner(null)
        }}
      />
    </div>
  )
}
