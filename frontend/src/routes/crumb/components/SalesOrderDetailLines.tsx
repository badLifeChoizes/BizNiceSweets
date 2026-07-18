// ABOUTME: Sales-order detail line grid (CRUMB-01, Phase 11b) — shows each ordered line with
// ABOUTME: ordered / reserved / shortage figures (shortage highlighted, non-stock lines flagged)
// ABOUTME: and, while the SO is Draft, in-place add / edit / delete over the SO line-CRUD hooks.

/**
 * SalesOrderDetailLines — the ordered-line grid on the sales-order detail screen.
 *
 * Props:
 *   soId    — the parent sales order.
 *   lines   — the SO's current ordered lines (from the SO detail query).
 *   isDraft — whether editing is allowed; the server rejects non-draft edits, and we mirror
 *             that by hiding the add form + per-row controls when false.
 *
 * Unlike the create-time SalesOrderLineEditor (a local-state builder), this mutates persisted
 * lines directly — mirroring QuoteLineEditor: each row is editable in place with a per-row Save
 * (useUpdateSoLine) and Delete (useDeleteSoLine), and a Draft-only add form (useAddSoLine).
 *
 * Every row shows its server-derived reserved qty, shortage, and line_total (Decimals as
 * STRINGS, D-11 — rendered as-is, never float math). A shortage > 0 is highlighted, and a
 * line with no stock item (item_id == null) carries a "Non-stock" flag. Every mutation toasts;
 * a 4xx surfaces the server reason.
 */

import { useState, useEffect } from 'react'
import { Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
import { cn } from '@/lib/utils'
import {
  useAddSoLine,
  useUpdateSoLine,
  useDeleteSoLine,
  type SalesOrderLine,
} from '../hooks'
import { usePlumParts } from './lookups'
import { getApiErrorMessage } from './apiError'

interface SalesOrderDetailLinesProps {
  soId: string
  lines: SalesOrderLine[]
  isDraft: boolean
}

// A qty/price string parsed for a decimal-safe ">0" test. Blank / non-numeric → 0.
function toNumber(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return n
}

// ─── One line row (editable while Draft) ────────────────────────────────────────

function SalesOrderLineRow({
  soId,
  line,
  isDraft,
  partName,
}: {
  soId: string
  line: SalesOrderLine
  isDraft: boolean
  partName: (id: string) => string
}) {
  const [qtyOrdered, setQtyOrdered] = useState(line.qty_ordered)
  const [unitPrice, setUnitPrice] = useState(line.unit_price)

  // Re-seed when the server sends fresh values (e.g. after a save or add).
  useEffect(() => {
    setQtyOrdered(line.qty_ordered)
    setUnitPrice(line.unit_price)
  }, [line.qty_ordered, line.unit_price])

  const updateMutation = useUpdateSoLine()
  const deleteMutation = useDeleteSoLine()

  const label = line.plum_part_id ? partName(line.plum_part_id) : (line.description ?? '—')
  const hasShortage = toNumber(line.shortage) > 0
  const nonStock = line.item_id == null
  const dirty = qtyOrdered !== line.qty_ordered || unitPrice !== line.unit_price

  function handleSave() {
    updateMutation.mutate(
      {
        soId,
        lineId: line.id,
        patch: {
          qty_ordered: qtyOrdered.trim(),
          unit_price: unitPrice.trim(),
        },
      },
      {
        onSuccess: () => toast.success('Line updated.'),
        onError: (err) => toast.error(getApiErrorMessage(err, 'Could not update the line.')),
      }
    )
  }

  function handleDelete() {
    deleteMutation.mutate(
      { soId, lineId: line.id },
      {
        onSuccess: () => toast.success('Line removed.'),
        onError: (err) => toast.error(getApiErrorMessage(err, 'Could not remove the line.')),
      }
    )
  }

  return (
    <TableRow className="h-12">
      <TableCell className="font-medium">
        <div className="flex items-center gap-2">
          <span>{label}</span>
          {nonStock && (
            <Badge variant="outline" className="text-muted-foreground">
              Non-stock
            </Badge>
          )}
        </div>
      </TableCell>
      <TableCell className="text-right">
        {isDraft ? (
          <Input
            aria-label="Quantity ordered"
            inputMode="decimal"
            className="w-24 text-right font-mono ml-auto"
            value={qtyOrdered}
            onChange={(e) => setQtyOrdered(e.target.value)}
          />
        ) : (
          <span className="font-mono">{line.qty_ordered}</span>
        )}
      </TableCell>
      <TableCell className="text-right">
        {isDraft ? (
          <Input
            aria-label="Unit price"
            inputMode="decimal"
            className="w-28 text-right font-mono ml-auto"
            value={unitPrice}
            onChange={(e) => setUnitPrice(e.target.value)}
          />
        ) : (
          <span className="font-mono">{line.unit_price}</span>
        )}
      </TableCell>
      <TableCell className="text-right font-mono">{line.qty_reserved}</TableCell>
      <TableCell className="text-right font-mono">{line.qty_shipped}</TableCell>
      <TableCell
        className={cn('text-right font-mono', hasShortage && 'font-semibold text-amber-600')}
      >
        {line.shortage}
      </TableCell>
      <TableCell className="text-right font-mono">{line.line_total}</TableCell>
      {isDraft && (
        <TableCell className="text-right">
          <div className="flex items-center justify-end gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={handleSave}
              disabled={!dirty || updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <Loader2 className="animate-spin" aria-hidden="true" />
              ) : (
                'Save'
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              aria-label="Delete line"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </TableCell>
      )}
    </TableRow>
  )
}

// ─── Add-line form (Draft only) ─────────────────────────────────────────────────

type AddMode = 'part' | 'free'

function AddLineForm({ soId }: { soId: string }) {
  const { data: parts = [] } = usePlumParts()
  const [mode, setMode] = useState<AddMode>('part')
  const [partId, setPartId] = useState('')
  const [description, setDescription] = useState('')
  const [qtyOrdered, setQtyOrdered] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')

  const addMutation = useAddSoLine()

  function reset() {
    setPartId('')
    setDescription('')
    setQtyOrdered('1')
    setUnitPrice('')
  }

  const canAdd =
    toNumber(qtyOrdered) > 0 &&
    unitPrice.trim() !== '' &&
    (mode === 'part' ? partId !== '' : description.trim() !== '')

  function handleAdd() {
    if (!canAdd) return
    const line =
      mode === 'part'
        ? {
            plum_part_id: partId,
            qty_ordered: qtyOrdered.trim(),
            unit_price: unitPrice.trim(),
          }
        : {
            description: description.trim(),
            qty_ordered: qtyOrdered.trim(),
            unit_price: unitPrice.trim(),
          }
    addMutation.mutate(
      { soId, line },
      {
        onSuccess: () => {
          toast.success('Line added.')
          reset()
        },
        onError: (err) => toast.error(getApiErrorMessage(err, 'Could not add the line.')),
      }
    )
  }

  return (
    <div className="space-y-4 rounded-md border border-border p-4">
      {/* Mode toggle */}
      <div className="flex gap-2">
        <Button
          type="button"
          variant={mode === 'part' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setMode('part')}
        >
          PLUM part
        </Button>
        <Button
          type="button"
          variant={mode === 'free' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setMode('free')}
        >
          Free text
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {mode === 'part' ? (
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="so-line-part">Part</Label>
            <Select value={partId} onValueChange={setPartId}>
              <SelectTrigger id="so-line-part" aria-label="Part">
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
        ) : (
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="so-line-description">Description</Label>
            <Input
              id="so-line-description"
              aria-label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Installation service"
            />
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="so-line-qty">Quantity</Label>
          <Input
            id="so-line-qty"
            aria-label="Quantity"
            inputMode="decimal"
            value={qtyOrdered}
            onChange={(e) => setQtyOrdered(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="so-line-price">Unit price</Label>
          <Input
            id="so-line-price"
            aria-label="Unit price"
            inputMode="decimal"
            value={unitPrice}
            onChange={(e) => setUnitPrice(e.target.value)}
            placeholder="e.g. 100.00"
          />
        </div>
      </div>

      <div className="flex justify-end">
        <Button
          variant="default"
          size="sm"
          onClick={handleAdd}
          disabled={!canAdd || addMutation.isPending}
        >
          {addMutation.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden="true" />
              Adding…
            </>
          ) : (
            'Add Line'
          )}
        </Button>
      </div>
    </div>
  )
}

// ─── Main grid ──────────────────────────────────────────────────────────────────

export function SalesOrderDetailLines({ soId, lines, isDraft }: SalesOrderDetailLinesProps) {
  const { data: parts = [] } = usePlumParts()
  const partName = (id: string) => parts.find((p) => p.id === id)?.part_number ?? id

  return (
    <div className="space-y-4">
      {lines.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No lines yet{isDraft ? ' — add a PLUM-part or free-text line below.' : '.'}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead className="text-right">Ordered</TableHead>
              <TableHead className="text-right">Unit price</TableHead>
              <TableHead className="text-right">Reserved</TableHead>
              <TableHead className="text-right">Shipped</TableHead>
              <TableHead className="text-right">Shortage</TableHead>
              <TableHead className="text-right">Line total</TableHead>
              {isDraft && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.map((line) => (
              <SalesOrderLineRow
                key={line.id}
                soId={soId}
                line={line}
                isDraft={isDraft}
                partName={partName}
              />
            ))}
          </TableBody>
        </Table>
      )}

      {isDraft && <AddLineForm soId={soId} />}
    </div>
  )
}
