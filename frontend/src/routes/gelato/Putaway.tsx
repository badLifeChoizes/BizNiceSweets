// ABOUTME: GELATO Putaway screen (/gelato/putaway) — location selector → list of
// ABOUTME: unbinned stock (item + unbinned qty) with a per-row "Put away" action that
// ABOUTME: opens a directed-putaway dialog (suggested bin + full-qty defaults).

/**
 * Putaway screen — GELATO directed putaway (/gelato/putaway).
 *
 * Layout: p-8 space-y-6 (matches the MOUSSE WorkOrders / GELATO Bins pattern).
 *
 * Flow (GELATO-01, D-P12a-10):
 *   1. Location Select at the top (active SYERP stock locations; first selected by
 *      default so single-location shops never touch it).
 *   2. Table of unbinned stock at that location: Item | Unbinned Qty | action.
 *      item_id is resolved to its inventory-item code/name (fetched once, mapped
 *      client-side); unbinned_qty is a Decimal STRING rendered as-is (D-11).
 *   3. "Put away" on a row opens PutawayDialog pre-filled with the suggested bin and
 *      the full unbinned qty; a successful putaway invalidates the unbinned list (via
 *      the mutation), so the row drops away on refresh.
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
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
import { apiClient } from '@/api/client'
import { GelatoNav } from '@/routes/gelato/components/GelatoNav'
import { PutawayDialog } from '@/routes/gelato/components/PutawayDialog'
import { useUnbinnedStock, type UnbinnedStock } from '@/routes/gelato/hooks'

// ─── Types ───────────────────────────────────────────────────────────────────

interface LocationOption {
  id: number
  name: string
  active: boolean
}

interface InventoryItemRow {
  id: string
  code: string
  name: string
}

// ─── API helpers ─────────────────────────────────────────────────────────────

// Active stock locations for the location Select. The list endpoint omits archived
// rows by default; we still guard on `active` in case that ever changes.
function fetchLocationOptions(): Promise<LocationOption[]> {
  return apiClient
    .get<LocationOption[]>('/api/v1/syerp/inventory/locations')
    .then((r) => r.data)
}

// Item master for id→code/name resolution (unbinned rows carry only item_id).
function fetchItems(): Promise<InventoryItemRow[]> {
  return apiClient
    .get<InventoryItemRow[]>('/api/v1/syerp/inventory/items')
    .then((r) => r.data)
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Putaway() {
  // ── Active location options ──
  const { data: locations = [] } = useQuery<LocationOption[], Error>({
    queryKey: ['syerp', 'inventory', 'locations', 'putaway-options'],
    queryFn: fetchLocationOptions,
    retry: false,
    staleTime: 60 * 1000,
  })
  const activeLocations = locations.filter((l) => l.active)

  // ── Item master for name resolution ──
  const { data: items = [] } = useQuery<InventoryItemRow[], Error>({
    queryKey: ['syerp', 'inventory', 'items', 'putaway-labels'],
    queryFn: fetchItems,
    retry: false,
    staleTime: 60 * 1000,
  })
  const itemLabel = (itemId: string): string => {
    const item = items.find((i) => i.id === itemId)
    return item ? `${item.code} · ${item.name}` : itemId
  }

  // ── Selected location (default to the first active one once loaded) ──
  const [locationId, setLocationId] = useState('')
  useEffect(() => {
    if (locationId || activeLocations.length === 0) return
    setLocationId(String(activeLocations[0].id))
  }, [locationId, activeLocations])

  const selectedLocationId = Number(locationId)

  // ── Unbinned stock at the selected location ──
  const { data: unbinned = [], isLoading } = useUnbinnedStock(selectedLocationId)

  // ── Dialog seam ──
  const [selected, setSelected] = useState<UnbinnedStock | null>(null)

  return (
    <div className="p-8 space-y-6">
      <GelatoNav />

      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Putaway</h1>
        <p className="text-sm text-muted-foreground">
          Move unbinned stock into bins. Each row suggests a target bin.
        </p>
      </div>

      {/* Location selector */}
      <div className="max-w-xs space-y-2">
        <Label htmlFor="putaway-location">Location</Label>
        <Select value={locationId} onValueChange={setLocationId}>
          <SelectTrigger id="putaway-location">
            <SelectValue placeholder="Select a location" />
          </SelectTrigger>
          <SelectContent>
            {activeLocations.map((loc) => (
              <SelectItem key={loc.id} value={String(loc.id)}>
                {loc.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Unbinned-stock table */}
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="animate-spin" aria-hidden="true" />
          Loading unbinned stock…
        </div>
      ) : unbinned.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {selectedLocationId
            ? 'No unbinned stock at this location.'
            : 'Select a location to view its unbinned stock.'}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead className="text-right">Unbinned Qty</TableHead>
              <TableHead className="w-32" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {unbinned.map((row) => (
              <TableRow key={row.item_id}>
                <TableCell className="font-medium">{itemLabel(row.item_id)}</TableCell>
                <TableCell className="text-right tabular-nums">{row.unbinned_qty}</TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm" onClick={() => setSelected(row)}>
                    Put away
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Directed-putaway dialog */}
      {selected && (
        <PutawayDialog
          itemId={selected.item_id}
          itemLabel={itemLabel(selected.item_id)}
          locationId={selectedLocationId}
          unbinnedQty={selected.unbinned_qty}
          open={selected !== null}
          onOpenChange={(open) => {
            if (!open) setSelected(null)
          }}
          onSuccess={() => setSelected(null)}
        />
      )}
    </div>
  )
}
