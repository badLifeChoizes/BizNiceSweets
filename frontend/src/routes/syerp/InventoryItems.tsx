// ABOUTME: SYERP Inventory Items screen (/syerp/inventory/items) — debounced
// ABOUTME: server search, Show-archived switch, and create/edit/archive/restore
// ABOUTME: over /api/v1/syerp/inventory/items. Structural twin of Vendors.tsx.

/**
 * InventoryItems screen — SYERP inventory item master data list (/syerp/inventory/items).
 *
 * Layout: p-8 space-y-6 (matches Vendors/Customers/Users pattern).
 *
 * Toolbar:
 *   - Search Input (server-side, debounced 300ms via ?q= param)
 *   - Show archived Switch (wires to include_archived query param)
 *   - Create Item Button (variant="default" — only accent element)
 *
 * Table columns: Name | Code | Unit | Status | Actions
 *
 * Row actions (DropdownMenu):
 *   - Edit    → opens InventoryItemSheet (edit mode)
 *   - Archive → opens ItemArchiveDialog (active rows only)
 *   - Restore → direct PATCH {active:true} + toast (archived rows only, no confirmation)
 *
 * Search: server-side via GET /api/v1/syerp/inventory/items?q={term}&include_archived={bool}
 * Query key: ['syerp', 'inventory', 'items', { q, includeArchived }]
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
import { InventoryItemSheet } from './components/InventoryItemSheet'
import { ItemArchiveDialog } from './components/ItemArchiveDialog'
import { SyerpNav } from './components/SyerpNav'
import type { InventoryItemRead } from './components/InventoryItemSheet'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchItems(q: string, includeArchived: boolean): Promise<InventoryItemRead[]> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (includeArchived) params.set('include_archived', 'true')
  return apiClient
    .get<InventoryItemRead[]>(`/api/v1/syerp/inventory/items?${params.toString()}`)
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

export function InventoryItems() {
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
  const [sheetItem, setSheetItem] = useState<InventoryItemRead | null>(null)

  // ── Archive dialog state ──
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [archiveItem, setArchiveItem] = useState<InventoryItemRead | null>(null)

  // ── Data ──
  const { data: items = [], isLoading, isError } = useQuery<InventoryItemRead[], Error>({
    queryKey: ['syerp', 'inventory', 'items', { q: searchFilter, includeArchived }],
    queryFn: () => fetchItems(searchFilter, includeArchived),
  })

  // ── Restore mutation ──
  const restoreMutation = useMutation<InventoryItemRead, Error, string>({
    mutationFn: (itemId) =>
      apiClient
        .patch<InventoryItemRead>(`/api/v1/syerp/inventory/items/${itemId}`, { active: true })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'inventory', 'items'] })
      toast('Item restored.')
    },
    onError: () => {
      toast.error('Failed to restore item. Please try again.')
    },
  })

  // ── Handlers ──
  function openCreateSheet() {
    setSheetMode('create')
    setSheetItem(null)
    setSheetOpen(true)
  }

  function openEditSheet(item: InventoryItemRead) {
    setSheetMode('edit')
    setSheetItem(item)
    setSheetOpen(true)
  }

  function openArchiveDialog(item: InventoryItemRead) {
    setArchiveItem(item)
    setArchiveOpen(true)
  }

  function handleRestore(item: InventoryItemRead) {
    restoreMutation.mutate(item.id)
  }

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      <SyerpNav />
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Inventory Items</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manage stock items. Items can optionally be linked to parts in PLUM.
        </p>
      </div>

      {/* Toolbar: Search + Show archived + Create Item */}
      <div className="flex items-center gap-4">
        <Input
          placeholder="Search items…"
          value={searchValue}
          onChange={handleSearchChange}
          className="max-w-xs"
          aria-label="Search items"
        />
        <div className="flex items-center gap-2">
          <Switch
            id="item-show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="item-show-archived">Show archived</Label>
        </div>
        {/* "Create Item" is the ONLY accent/default button on this screen */}
        <Button variant="default" onClick={openCreateSheet} className="ml-auto">
          Create Item
        </Button>
      </div>

      {/* Items table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load items. Check your connection and refresh the page.
          </p>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          {searchFilter ? (
            <>
              <p className="text-base font-semibold text-foreground">No items found</p>
              <p className="text-sm text-muted-foreground">
                No items match your search. Clear the filter or create a new item.
              </p>
            </>
          ) : (
            <>
              <p className="text-base font-semibold text-foreground">No items yet</p>
              <p className="text-sm text-muted-foreground">
                Add your first item to get started.
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
              <TableHead>Unit</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id} className="h-12">
                <TableCell className="font-medium">{item.name}</TableCell>
                <TableCell>{item.code}</TableCell>
                <TableCell>{item.unit_of_measure}</TableCell>
                <TableCell>
                  <StatusBadge active={item.active} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Item actions for ${item.name}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditSheet(item)}>
                        Edit
                      </DropdownMenuItem>
                      {item.active ? (
                        <DropdownMenuItem
                          onClick={() => openArchiveDialog(item)}
                          className="text-destructive focus:text-destructive"
                        >
                          Archive
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => handleRestore(item)}>
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
      <InventoryItemSheet
        open={sheetOpen}
        mode={sheetMode}
        item={sheetItem}
        onClose={() => setSheetOpen(false)}
      />

      {/* ─── Archive Confirmation Dialog ──────────────────────────────────── */}
      <ItemArchiveDialog
        open={archiveOpen}
        item={archiveItem}
        onClose={() => {
          setArchiveOpen(false)
          setArchiveItem(null)
        }}
      />
    </div>
  )
}
