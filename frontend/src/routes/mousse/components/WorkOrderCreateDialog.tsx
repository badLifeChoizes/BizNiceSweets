// ABOUTME: Create-a-work-order dialog (MOUSSE-01, SC7) — pick the PLUM part to build,
// ABOUTME: a planned quantity, and the target stock location, then POST /mousse/work-orders.
// ABOUTME: On success invalidates the work-order list query and toasts; 4xx surface a toast.

/**
 * WorkOrderCreateDialog — opens a new Draft work order (MOUSSE-01, SC7).
 *
 * Props:
 *   open / onOpenChange — Radix-controlled visibility.
 *
 * Fields:
 *   1. Part — required Select of PLUM parts (GET /api/v1/plum/parts). The FG to build.
 *   2. Planned qty — positive Decimal, kept as a STRING and sent verbatim (D-11).
 *   3. Target location — required Select of active stock locations
 *      (GET /api/v1/syerp/inventory/locations).
 *
 * Mutation: POST /api/v1/mousse/work-orders with { plum_part_id, planned_qty,
 *   target_location_id }. Success: invalidate ['mousse','work-orders'], toast, close.
 *   Error (e.g. 422 bad qty): toast.error(server detail) and DO NOT close so the user
 *   can correct the input.
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { apiClient } from '@/api/client'
import { workOrdersKey, type WorkOrderRead } from '../hooks'
import type { PartRead } from '../../plum/components/PartSheet'
import type { StockLocationRead } from '../../syerp/components/StockLocationSheet'

// ─── Types ───────────────────────────────────────────────────────────────────

interface WorkOrderCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface WorkOrderCreatePayload {
  plum_part_id: string
  planned_qty: string
  target_location_id: number
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchParts(): Promise<PartRead[]> {
  return apiClient.get<PartRead[]>('/api/v1/plum/parts').then((r) => r.data)
}

function fetchLocations(): Promise<StockLocationRead[]> {
  return apiClient
    .get<StockLocationRead[]>('/api/v1/syerp/inventory/locations')
    .then((r) => r.data)
}

// Surface the server's real reason instead of a generic "please try again". FastAPI
// returns either a string `detail` or a 422 validation array of { loc, msg }.
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

// A qty string parsed for a decimal-safe ">0" test. Blank / non-numeric → 0.
function toNumber(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return n
}

// ─── Main component ──────────────────────────────────────────────────────────

export function WorkOrderCreateDialog({ open, onOpenChange }: WorkOrderCreateDialogProps) {
  const queryClient = useQueryClient()

  // ── Options ──
  const { data: parts = [] } = useQuery<PartRead[], Error>({
    queryKey: ['plum', 'parts'],
    queryFn: fetchParts,
    enabled: open,
    staleTime: 60 * 1000,
  })

  const { data: locations = [] } = useQuery<StockLocationRead[], Error>({
    queryKey: ['syerp', 'inventory', 'locations'],
    queryFn: fetchLocations,
    enabled: open,
    staleTime: 60 * 1000,
  })
  const activeLocations = locations.filter((l) => l.active)

  // ── Form state ──
  const [partId, setPartId] = useState('')
  const [plannedQty, setPlannedQty] = useState('')
  const [locationId, setLocationId] = useState('')

  // ── Reset the form each time the dialog opens ──
  useEffect(() => {
    if (!open) return
    setPartId('')
    setPlannedQty('')
    setLocationId('')
  }, [open])

  // ── Validation ──
  const canSubmit = partId !== '' && locationId !== '' && toNumber(plannedQty) > 0

  // ── Mutation ──
  const createMutation = useMutation<WorkOrderRead, Error, WorkOrderCreatePayload>({
    mutationFn: (payload) =>
      apiClient
        .post<WorkOrderRead>('/api/v1/mousse/work-orders', payload)
        .then((r) => r.data),
    onSuccess: (wo) => {
      void queryClient.invalidateQueries({ queryKey: workOrdersKey })
      toast.success(`Work order ${wo.wo_number} created.`)
      onOpenChange(false)
    },
    onError: (err) => {
      // Keep the dialog open so the user can correct the input.
      toast.error(getApiErrorMessage(err, 'Failed to create the work order. Please try again.'))
    },
  })

  const isSaving = createMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    createMutation.mutate({
      plum_part_id: partId,
      planned_qty: plannedQty.trim(),
      target_location_id: Number(locationId),
    })
  }

  // ── Render ──
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="wo-create-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New Work Order</DialogTitle>
          <DialogDescription id="wo-create-description">
            Choose the part to build, a planned quantity, and the stock location the
            finished goods will land in. The order is created as a Draft.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Part */}
          <div className="space-y-2">
            <Label htmlFor="wo-part">Part</Label>
            <Select value={partId} onValueChange={setPartId}>
              <SelectTrigger id="wo-part" aria-label="Part">
                <SelectValue placeholder="Select a part" />
              </SelectTrigger>
              <SelectContent>
                {parts.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.part_number}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Planned qty */}
          <div className="space-y-2">
            <Label htmlFor="wo-planned-qty">Planned qty</Label>
            <Input
              id="wo-planned-qty"
              aria-label="Planned qty"
              inputMode="decimal"
              value={plannedQty}
              onChange={(e) => setPlannedQty(e.target.value)}
              placeholder="e.g. 10"
            />
          </div>

          {/* Target location */}
          <div className="space-y-2">
            <Label htmlFor="wo-location">Target location</Label>
            <Select value={locationId} onValueChange={setLocationId}>
              <SelectTrigger id="wo-location" aria-label="Target location">
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
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Creating…
              </>
            ) : (
              'Create Work Order'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
