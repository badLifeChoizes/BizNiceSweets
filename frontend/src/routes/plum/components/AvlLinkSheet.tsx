/**
 * AvlLinkSheet — create/edit form for Approved Vendor List (AVL) vendor links.
 *
 * Props:
 *   open: boolean — controls sheet visibility
 *   mode: 'create' | 'edit' — determines title and mutation used
 *   partId: string — parent part ID
 *   existingLink?: AvlLinkRead | null — pre-populated for edit mode
 *   onClose: () => void — called on Save success or Discard
 *
 * Fields:
 *   1. Vendor — server-side search combobox (GET /api/v1/syerp/partners?is_vendor=true&q=, debounced 300ms)
 *   2. Vendor Part Number — optional input
 *   3. Preferred — Switch, multiple preferred vendors allowed
 *   4. Notes — optional input
 *   --- Separator ---
 *   5. Price Breaks — PriceBreakEditor embedded sub-section
 *
 * Mutations:
 *   Create: POST /api/v1/plum/parts/{partId}/avl
 *   Edit:   PATCH /api/v1/plum/parts/{partId}/avl/{linkId}
 *   onSuccess: invalidate ['plum','parts',partId], toast
 *   onError: getApiErrorMessage default fallback
 *
 * Currency: read locale.currency from GET /api/v1/core/settings (PartnerSheet.tsx idiom).
 *
 * Accessibility: every input has a paired Label; Sheet has aria-labelledby + aria-describedby.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { apiClient } from '@/api/client'
import { PriceBreakEditor, type PriceBreakRow } from './PriceBreakEditor'
import type { SettingRecord } from '@/hooks/useSettings'

// ─── Types ───────────────────────────────────────────────────────────────────

interface VendorSearchResult {
  id: string
  code: string
  name: string
  is_vendor: boolean
  active: boolean
}

interface PriceBreakRead {
  id: string
  avl_link_id: string
  qty_threshold: number
  unit_cost: number | string
  lead_days?: number | null
  sort_order: number
}

export interface AvlLinkRead {
  id: string
  part_id: string
  vendor_id: string
  vendor_name?: string
  vendor_code?: string
  vendor_part_number?: string | null
  preferred: boolean
  notes?: string | null
  active: boolean
  price_breaks: PriceBreakRead[]
}

interface AvlLinkSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  partId: string
  existingLink?: AvlLinkRead | null
  onClose: () => void
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

// ─── Convert PriceBreakRead[] to PriceBreakRow[] ─────────────────────────────
function toPriceBreakRows(reads: PriceBreakRead[]): PriceBreakRow[] {
  return reads
    .slice()
    .sort((a, b) => a.sort_order - b.sort_order)
    .map((pb) => ({
      qty_threshold: pb.qty_threshold,
      unit_cost: typeof pb.unit_cost === 'string' ? parseFloat(pb.unit_cost) : pb.unit_cost,
      lead_days: pb.lead_days ?? null,
    }))
}

// ─── Main component ──────────────────────────────────────────────────────────

export function AvlLinkSheet({
  open,
  mode,
  partId,
  existingLink,
  onClose,
}: AvlLinkSheetProps) {
  const queryClient = useQueryClient()

  // ── Settings fetch for currency ──
  const { data: settings = [] } = useQuery<SettingRecord[], Error>({
    queryKey: ['core', 'settings'],
    queryFn: () =>
      apiClient.get<SettingRecord[]>('/api/v1/core/settings').then((r) => r.data),
    staleTime: 5 * 60 * 1000,
  })

  function getSystemCurrency(): string {
    const rec = settings.find((s) => s.key === 'locale.currency')
    return rec?.value ?? 'USD'
  }

  // ── Form state ──
  const [formVendorId, setFormVendorId] = useState('')
  const [formVendorDisplay, setFormVendorDisplay] = useState('')
  const [formVendorPartNumber, setFormVendorPartNumber] = useState('')
  const [formPreferred, setFormPreferred] = useState(false)
  const [formNotes, setFormNotes] = useState('')
  const [priceBreaks, setPriceBreaks] = useState<PriceBreakRow[]>([])

  // ── Vendor search state ──
  const [vendorSearchQuery, setVendorSearchQuery] = useState('')
  const [showVendorResults, setShowVendorResults] = useState(false)
  const vendorDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [debouncedVendorQuery, setDebouncedVendorQuery] = useState('')

  const handleVendorSearchInput = useCallback((value: string) => {
    setVendorSearchQuery(value)
    if (vendorDebounceRef.current) clearTimeout(vendorDebounceRef.current)
    vendorDebounceRef.current = setTimeout(() => {
      setDebouncedVendorQuery(value)
      setShowVendorResults(true)
    }, 300)
  }, [])

  // ── Vendor search query ──
  const { data: vendorResults = [] } = useQuery<VendorSearchResult[], Error>({
    queryKey: ['syerp', 'partners', 'vendor-search', debouncedVendorQuery],
    queryFn: () =>
      apiClient
        .get<VendorSearchResult[]>('/api/v1/syerp/partners', {
          params: { role: 'vendor', q: debouncedVendorQuery },
        })
        .then((r) => r.data),
    enabled: !!debouncedVendorQuery && debouncedVendorQuery.length >= 1,
  })

  // ── Populate form when sheet opens ──
  useEffect(() => {
    if (!open) return

    setShowVendorResults(false)
    setVendorSearchQuery('')
    setDebouncedVendorQuery('')

    if (mode === 'create') {
      setFormVendorId('')
      setFormVendorDisplay('')
      setFormVendorPartNumber('')
      setFormPreferred(false)
      setFormNotes('')
      setPriceBreaks([])
    } else if (mode === 'edit' && existingLink) {
      setFormVendorId(existingLink.vendor_id)
      const vendorDisplay = existingLink.vendor_code
        ? `${existingLink.vendor_code} — ${existingLink.vendor_name ?? ''}`
        : (existingLink.vendor_name ?? existingLink.vendor_id)
      setFormVendorDisplay(vendorDisplay)
      setVendorSearchQuery(vendorDisplay)
      setFormVendorPartNumber(existingLink.vendor_part_number ?? '')
      setFormPreferred(existingLink.preferred)
      setFormNotes(existingLink.notes ?? '')
      setPriceBreaks(toPriceBreakRows(existingLink.price_breaks))
    }
  }, [open, mode, existingLink])

  // ── Select a vendor from search results ──
  function selectVendor(vendor: VendorSearchResult) {
    setFormVendorId(vendor.id)
    const display = `${vendor.code} — ${vendor.name}`
    setFormVendorDisplay(display)
    setVendorSearchQuery(display)
    setShowVendorResults(false)
  }

  // ── Mutations ──
  interface AvlCreatePayload {
    vendor_id: string
    vendor_part_number?: string
    preferred: boolean
    notes?: string
    price_breaks?: PriceBreakRow[]
  }

  interface AvlUpdatePayload {
    vendor_part_number?: string | null
    preferred?: boolean
    notes?: string | null
    price_breaks?: PriceBreakRow[]
  }

  const createMutation = useMutation<unknown, Error, AvlCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post(`/api/v1/plum/parts/${partId}/avl`, payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      toast('Vendor link added.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save vendor link. Please try again.'))
    },
  })

  const editMutation = useMutation<unknown, Error, AvlUpdatePayload>({
    mutationFn: (payload) =>
      apiClient
        .patch(`/api/v1/plum/parts/${partId}/avl/${existingLink?.id}`, payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
      toast('Vendor link updated.')
      onClose()
    },
    onError: (err) => {
      toast.error(getApiErrorMessage(err, 'Failed to save vendor link. Please try again.'))
    },
  })

  const isSaving = createMutation.isPending || editMutation.isPending

  function handleSave() {
    if (!formVendorId) {
      toast.error('Vendor is required.')
      return
    }
    const currency = getSystemCurrency()
    // Sort price breaks by qty_threshold ascending before saving
    const sortedBreaks = priceBreaks
      .slice()
      .sort((a, b) => a.qty_threshold - b.qty_threshold)
      .map((pb) => ({
        qty_threshold: pb.qty_threshold,
        unit_cost: pb.unit_cost,
        lead_days: pb.lead_days,
        _currency: currency,
      }))
      .map(({ _currency: _c, ...rest }) => rest) // strip internal field

    if (mode === 'create') {
      createMutation.mutate({
        vendor_id: formVendorId,
        vendor_part_number: formVendorPartNumber || undefined,
        preferred: formPreferred,
        notes: formNotes || undefined,
        price_breaks: sortedBreaks,
      })
    } else {
      editMutation.mutate({
        vendor_part_number: formVendorPartNumber || null,
        preferred: formPreferred,
        notes: formNotes || null,
        price_breaks: sortedBreaks,
      })
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  const sheetTitle = mode === 'create' ? 'Add Vendor Link' : 'Edit Vendor Link'
  const sheetDescription =
    mode === 'create'
      ? 'Search for a vendor and set pricing and preferences.'
      : 'Update the vendor link details, preferences, and price breaks.'

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        aria-labelledby="avl-sheet-title"
        aria-describedby="avl-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="avl-sheet-title">{sheetTitle}</SheetTitle>
          <SheetDescription id="avl-sheet-description">
            {sheetDescription}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6">
          {/* ─── Section 1: Vendor ─────────────────────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="avl-vendor">
                Vendor
                <span className="text-destructive ml-1" aria-hidden="true">*</span>
              </Label>
              <div className="relative">
                <Input
                  id="avl-vendor"
                  value={vendorSearchQuery}
                  onChange={(e) => {
                    if (mode === 'create') {
                      handleVendorSearchInput(e.target.value)
                      if (formVendorId) {
                        setFormVendorId('')
                        setFormVendorDisplay('')
                      }
                    }
                  }}
                  onFocus={() => {
                    if (debouncedVendorQuery && vendorResults.length > 0) {
                      setShowVendorResults(true)
                    }
                  }}
                  placeholder="Search vendor…"
                  disabled={mode === 'edit'}
                  autoComplete="off"
                />
                {showVendorResults && vendorResults.length > 0 && mode === 'create' && (
                  <div className="absolute z-10 w-full mt-1 bg-popover border border-border rounded-md shadow-md max-h-48 overflow-y-auto">
                    {vendorResults
                      .filter((v) => v.is_vendor && v.active)
                      .map((vendor) => (
                        <button
                          key={vendor.id}
                          type="button"
                          className="w-full px-3 py-2 text-left hover:bg-muted flex flex-col"
                          onClick={() => selectVendor(vendor)}
                        >
                          <span className="font-medium text-sm text-foreground">
                            {vendor.code}
                          </span>
                          <span className="text-xs text-muted-foreground">{vendor.name}</span>
                        </button>
                      ))}
                  </div>
                )}
              </div>
              {mode === 'edit' && formVendorDisplay && (
                <p className="text-sm text-muted-foreground">{formVendorDisplay}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="avl-vendor-part-number">Vendor Part Number</Label>
              <Input
                id="avl-vendor-part-number"
                value={formVendorPartNumber}
                onChange={(e) => setFormVendorPartNumber(e.target.value)}
                placeholder="e.g. MFR-12345"
              />
              <p className="text-xs text-muted-foreground">
                The supplier&apos;s part number or catalog reference.
              </p>
            </div>

            {/* Preferred switch */}
            <div className="flex items-center gap-3">
              <Switch
                id="avl-preferred"
                checked={formPreferred}
                onCheckedChange={setFormPreferred}
              />
              <Label htmlFor="avl-preferred">Preferred vendor</Label>
            </div>
            <p className="text-xs text-muted-foreground -mt-2">
              Mark this vendor as a preferred sourcing option. Multiple preferred vendors are allowed.
            </p>

            <div className="space-y-2">
              <Label htmlFor="avl-notes">Notes</Label>
              <Input
                id="avl-notes"
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="e.g. lead time notes"
              />
            </div>
          </div>

          <Separator />

          {/* ─── Section 2: Price Breaks ──────────────────────────────── */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-foreground">Price Breaks</h3>
            <PriceBreakEditor
              rows={priceBreaks}
              onChange={setPriceBreaks}
            />
          </div>
        </div>

        <SheetFooter className="flex gap-2 pt-4">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Discard Changes
          </Button>
          <Button variant="default" onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Saving…
              </>
            ) : (
              'Save Vendor Link'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
