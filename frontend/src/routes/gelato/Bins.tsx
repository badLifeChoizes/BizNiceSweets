// ABOUTME: GELATO Bins screen (/gelato/bins) — pick a stock location, then list /
// ABOUTME: create / edit / archive its bins. A Show-archived Switch drives the
// ABOUTME: include_archived query param. Mirrors syerp/StockLocations.tsx.

/**
 * Bins screen — GELATO bin master data within a SYERP stock location (GELATO-01).
 *
 * Layout: p-8 space-y-6 (matches StockLocations/InventoryItems pattern).
 *
 * Toolbar:
 *   - Location Select (populated from active SYERP stock locations) — bins load
 *     once a location is chosen; nothing renders until then.
 *   - Show archived Switch (drives the include_archived query param via useBins)
 *   - Create Bin Button (variant="default" — only accent element; disabled until
 *     a location is selected)
 *
 * Table columns: Code | Description | Status | Actions
 *
 * Row actions (DropdownMenu):
 *   - Edit    → opens BinSheet (edit mode)
 *   - Archive → useArchiveBin direct mutation + toast (active rows only)
 *
 * Data hooks live in ./hooks (useBins / useCreateBin / useUpdateBin /
 * useArchiveBin). Server 4xx from create/edit surfaces in BinSheet; archive
 * errors surface here via toast.error.
 *
 * Accessibility: row aria-label, color+text status badge, decorative icon aria-hidden.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MoreHorizontal, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
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
import type { StockLocationRead } from '@/routes/syerp/components/StockLocationSheet'
import { GelatoNav } from './components/GelatoNav'
import { BinSheet } from './components/BinSheet'
import { useBins, useArchiveBin } from './hooks'
import type { Bin } from './hooks'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchLocations(): Promise<StockLocationRead[]> {
  return apiClient
    .get<StockLocationRead[]>('/api/v1/syerp/inventory/locations')
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

export function Bins() {
  // ── Location selector ──
  const [locationId, setLocationId] = useState('')
  const selectedLocationId = locationId ? Number(locationId) : 0

  // ── Show archived toggle ──
  const [includeArchived, setIncludeArchived] = useState(false)

  // ── Sheet state ──
  const [sheetOpen, setSheetOpen] = useState(false)
  const [sheetMode, setSheetMode] = useState<'create' | 'edit'>('create')
  const [sheetBin, setSheetBin] = useState<Bin | null>(null)

  // ── Location options ──
  const { data: locations = [] } = useQuery<StockLocationRead[], Error>({
    queryKey: ['syerp', 'inventory', 'locations'],
    queryFn: fetchLocations,
    staleTime: 60 * 1000,
  })
  const activeLocations = locations.filter((l) => l.active)

  // ── Bins for the selected location ──
  const {
    data: bins = [],
    isLoading,
    isError,
  } = useBins(selectedLocationId, includeArchived)

  // ── Archive mutation ──
  const archiveBin = useArchiveBin()

  // ── Handlers ──
  function openCreateSheet() {
    setSheetMode('create')
    setSheetBin(null)
    setSheetOpen(true)
  }

  function openEditSheet(bin: Bin) {
    setSheetMode('edit')
    setSheetBin(bin)
    setSheetOpen(true)
  }

  function handleArchive(bin: Bin) {
    archiveBin.mutate(bin.id, {
      onSuccess: () => toast('Bin archived.'),
      onError: () => toast.error('Failed to archive bin. Please try again.'),
    })
  }

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      <GelatoNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Bins</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manage the storage bins that subdivide a stock location.
        </p>
      </div>

      {/* Toolbar: Location + Show archived + Create Bin */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Label htmlFor="bin-location">Location</Label>
          <Select value={locationId} onValueChange={setLocationId}>
            <SelectTrigger id="bin-location" aria-label="Location" className="w-56">
              <SelectValue placeholder="Select a location" />
            </SelectTrigger>
            <SelectContent>
              {activeLocations.map((l) => (
                <SelectItem key={l.id} value={String(l.id)}>
                  {l.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="bin-show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="bin-show-archived">Show archived</Label>
        </div>
        {/* "Create Bin" is the ONLY accent/default button on this screen */}
        <Button
          variant="default"
          onClick={openCreateSheet}
          disabled={!selectedLocationId}
          className="ml-auto"
        >
          Create Bin
        </Button>
      </div>

      {/* Bins table / prompt / loading / empty states */}
      {!selectedLocationId ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Select a location to view and manage its bins.
          </p>
        </div>
      ) : isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load bins. Check your connection and refresh the page.
          </p>
        </div>
      ) : bins.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No bins yet</p>
          <p className="text-sm text-muted-foreground">Add your first bin to get started.</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bins.map((bin) => (
              <TableRow key={bin.id} className="h-12">
                <TableCell className="font-medium">{bin.code}</TableCell>
                <TableCell className="text-muted-foreground">{bin.description ?? '—'}</TableCell>
                <TableCell>
                  <StatusBadge active={bin.active} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Bin actions for ${bin.code}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditSheet(bin)}>Edit</DropdownMenuItem>
                      {bin.active && (
                        <DropdownMenuItem
                          onClick={() => handleArchive(bin)}
                          className="text-destructive focus:text-destructive"
                        >
                          Archive
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
      <BinSheet
        open={sheetOpen}
        mode={sheetMode}
        locationId={selectedLocationId}
        bin={sheetBin}
        onClose={() => setSheetOpen(false)}
      />
    </div>
  )
}
