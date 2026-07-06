// ABOUTME: SYERP Stock Locations screen (/syerp/inventory/locations) — a Show-
// ABOUTME: archived switch plus create/edit/archive/restore over
// ABOUTME: /api/v1/syerp/inventory/locations. Name-only twin of InventoryItems.tsx.

/**
 * StockLocations screen — SYERP stock location master data list.
 *
 * Layout: p-8 space-y-6 (matches InventoryItems/Vendors/Customers pattern).
 *
 * Toolbar:
 *   - Show archived Switch (wires to include_archived query param)
 *   - Create Location Button (variant="default" — only accent element)
 *
 * A location is just a unique name + active flag — there is no code and the
 * backend list has no search param, so this screen has no search box.
 *
 * Table columns: Name | Status | Actions
 *
 * Row actions (DropdownMenu):
 *   - Edit    → opens StockLocationSheet (edit mode)
 *   - Archive → opens StockLocationArchiveDialog (active rows only)
 *   - Restore → direct PATCH {active:true} + toast (archived rows only, no confirmation)
 *
 * Query key: ['syerp', 'inventory', 'locations', { includeArchived }]
 *
 * Accessibility: row aria-label, color+text status badge, decorative icon aria-hidden.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MoreHorizontal, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
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
import { StockLocationSheet } from './components/StockLocationSheet'
import { StockLocationArchiveDialog } from './components/StockLocationArchiveDialog'
import { SyerpNav } from './components/SyerpNav'
import type { StockLocationRead } from './components/StockLocationSheet'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchLocations(includeArchived: boolean): Promise<StockLocationRead[]> {
  const params = new URLSearchParams()
  if (includeArchived) params.set('include_archived', 'true')
  return apiClient
    .get<StockLocationRead[]>(`/api/v1/syerp/inventory/locations?${params.toString()}`)
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

export function StockLocations() {
  const queryClient = useQueryClient()

  // ── Show archived toggle ──
  const [includeArchived, setIncludeArchived] = useState(false)

  // ── Sheet state ──
  const [sheetOpen, setSheetOpen] = useState(false)
  const [sheetMode, setSheetMode] = useState<'create' | 'edit'>('create')
  const [sheetLocation, setSheetLocation] = useState<StockLocationRead | null>(null)

  // ── Archive dialog state ──
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [archiveLocation, setArchiveLocation] = useState<StockLocationRead | null>(null)

  // ── Data ──
  const {
    data: locations = [],
    isLoading,
    isError,
  } = useQuery<StockLocationRead[], Error>({
    queryKey: ['syerp', 'inventory', 'locations', { includeArchived }],
    queryFn: () => fetchLocations(includeArchived),
  })

  // ── Restore mutation ──
  const restoreMutation = useMutation<StockLocationRead, Error, number>({
    mutationFn: (locationId) =>
      apiClient
        .patch<StockLocationRead>(`/api/v1/syerp/inventory/locations/${locationId}`, {
          active: true,
        })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'locations'] })
      toast('Location restored.')
    },
    onError: () => {
      toast.error('Failed to restore location. Please try again.')
    },
  })

  // ── Handlers ──
  function openCreateSheet() {
    setSheetMode('create')
    setSheetLocation(null)
    setSheetOpen(true)
  }

  function openEditSheet(location: StockLocationRead) {
    setSheetMode('edit')
    setSheetLocation(location)
    setSheetOpen(true)
  }

  function openArchiveDialog(location: StockLocationRead) {
    setArchiveLocation(location)
    setArchiveOpen(true)
  }

  function handleRestore(location: StockLocationRead) {
    restoreMutation.mutate(location.id)
  }

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Stock Locations</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manage the physical or logical locations where stock is held.
        </p>
      </div>

      {/* Toolbar: Show archived + Create Location */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Switch
            id="location-show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="location-show-archived">Show archived</Label>
        </div>
        {/* "Create Location" is the ONLY accent/default button on this screen */}
        <Button variant="default" onClick={openCreateSheet} className="ml-auto">
          Create Location
        </Button>
      </div>

      {/* Locations table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load locations. Check your connection and refresh the page.
          </p>
        </div>
      ) : locations.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No locations yet</p>
          <p className="text-sm text-muted-foreground">Add your first location to get started.</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {locations.map((location) => (
              <TableRow key={location.id} className="h-12">
                <TableCell className="font-medium">{location.name}</TableCell>
                <TableCell>
                  <StatusBadge active={location.active} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Location actions for ${location.name}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditSheet(location)}>
                        Edit
                      </DropdownMenuItem>
                      {location.active ? (
                        <DropdownMenuItem
                          onClick={() => openArchiveDialog(location)}
                          className="text-destructive focus:text-destructive"
                        >
                          Archive
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => handleRestore(location)}>
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
      <StockLocationSheet
        open={sheetOpen}
        mode={sheetMode}
        location={sheetLocation}
        onClose={() => setSheetOpen(false)}
      />

      {/* ─── Archive Confirmation Dialog ──────────────────────────────────── */}
      <StockLocationArchiveDialog
        open={archiveOpen}
        location={archiveLocation}
        onClose={() => {
          setArchiveOpen(false)
          setArchiveLocation(null)
        }}
      />
    </div>
  )
}
