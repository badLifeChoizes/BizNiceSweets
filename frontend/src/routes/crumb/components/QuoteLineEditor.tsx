// ABOUTME: Quote line editor (CRUMB-01) — add PLUM-part lines (server defaults unit_price
// ABOUTME: from released cost + markup, returned editable) or free-text lines, and edit /
// ABOUTME: delete lines while the quote is Draft. Non-draft edits 409 and surface as toasts.

/**
 * QuoteLineEditor — the priced-line grid on the quote detail screen.
 *
 * Props:
 *   quoteId — the parent quote.
 *   lines   — the quote's current priced lines (from the quote detail query).
 *   isDraft — whether editing is allowed; the server 409s otherwise, and we mirror that
 *             by hiding the add form + per-row controls when false.
 *
 * Add form (Draft only) toggles between:
 *   - PLUM part: pick a part + quantity + optional markup %. unit_price is omitted so the
 *     server derives it (released cost + markup); the created line comes back priced and
 *     that unit_price is then editable in the row.
 *   - Free text: description + quantity + an explicit unit_price.
 *
 * Each row shows its line_total (service-derived, D-11); rows are editable in place with a
 * per-row Save (useUpdateQuoteLine) and Delete (useDeleteQuoteLine). Every mutation toasts;
 * a 4xx surfaces the server reason.
 */

import { useState, useEffect } from 'react'
import { Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
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
import {
  useAddQuoteLine,
  useUpdateQuoteLine,
  useDeleteQuoteLine,
  type QuoteLine,
} from '../hooks'
import { usePlumParts } from './lookups'
import { getApiErrorMessage } from './apiError'

interface QuoteLineEditorProps {
  quoteId: string
  lines: QuoteLine[]
  isDraft: boolean
}

// A qty/price string parsed for a decimal-safe ">0" test. Blank / non-numeric → 0.
function toNumber(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return n
}

// ─── One editable line row ─────────────────────────────────────────────────────

function QuoteLineRow({
  quoteId,
  line,
  isDraft,
  partName,
}: {
  quoteId: string
  line: QuoteLine
  isDraft: boolean
  partName: (id: string) => string
}) {
  const [quantity, setQuantity] = useState(line.quantity)
  const [unitPrice, setUnitPrice] = useState(line.unit_price)
  const [markupPct, setMarkupPct] = useState(line.markup_pct ?? '')

  // Re-seed when the server sends fresh values (e.g. after a save or add).
  useEffect(() => {
    setQuantity(line.quantity)
    setUnitPrice(line.unit_price)
    setMarkupPct(line.markup_pct ?? '')
  }, [line.quantity, line.unit_price, line.markup_pct])

  const updateMutation = useUpdateQuoteLine()
  const deleteMutation = useDeleteQuoteLine()

  const label = line.plum_part_id ? partName(line.plum_part_id) : (line.description ?? '—')
  const dirty =
    quantity !== line.quantity ||
    unitPrice !== line.unit_price ||
    markupPct !== (line.markup_pct ?? '')

  function handleSave() {
    updateMutation.mutate(
      {
        quoteId,
        lineId: line.id,
        patch: {
          quantity: quantity.trim(),
          unit_price: unitPrice.trim() || null,
          markup_pct: markupPct.trim() || null,
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
      { quoteId, lineId: line.id },
      {
        onSuccess: () => toast.success('Line removed.'),
        onError: (err) => toast.error(getApiErrorMessage(err, 'Could not remove the line.')),
      }
    )
  }

  return (
    <TableRow className="h-12">
      <TableCell className="font-medium">{label}</TableCell>
      <TableCell className="text-right">
        {isDraft ? (
          <Input
            aria-label="Quantity"
            inputMode="decimal"
            className="w-24 text-right font-mono ml-auto"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        ) : (
          <span className="font-mono">{line.quantity}</span>
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
      <TableCell className="text-right">
        {isDraft ? (
          <Input
            aria-label="Markup percent"
            inputMode="decimal"
            className="w-20 text-right font-mono ml-auto"
            value={markupPct}
            onChange={(e) => setMarkupPct(e.target.value)}
            placeholder="—"
          />
        ) : (
          <span className="font-mono">{line.markup_pct ?? '—'}</span>
        )}
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

function AddLineForm({ quoteId }: { quoteId: string }) {
  const { data: parts = [] } = usePlumParts()
  const [mode, setMode] = useState<AddMode>('part')
  const [partId, setPartId] = useState('')
  const [description, setDescription] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')
  const [markupPct, setMarkupPct] = useState('')

  const addMutation = useAddQuoteLine()

  function reset() {
    setPartId('')
    setDescription('')
    setQuantity('1')
    setUnitPrice('')
    setMarkupPct('')
  }

  const canAdd =
    toNumber(quantity) > 0 &&
    (mode === 'part' ? partId !== '' : description.trim() !== '' && unitPrice.trim() !== '')

  function handleAdd() {
    if (!canAdd) return
    const line =
      mode === 'part'
        ? {
            plum_part_id: partId,
            quantity: quantity.trim(),
            markup_pct: markupPct.trim() || null,
          }
        : {
            description: description.trim(),
            quantity: quantity.trim(),
            unit_price: unitPrice.trim(),
          }
    addMutation.mutate(
      { quoteId, line },
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
            <Label htmlFor="add-part">Part</Label>
            <Select value={partId} onValueChange={setPartId}>
              <SelectTrigger id="add-part" aria-label="Part">
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
            <Label htmlFor="add-description">Description</Label>
            <Input
              id="add-description"
              aria-label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Installation service"
            />
          </div>
        )}

        <div className="space-y-2">
          <Label htmlFor="add-qty">Quantity</Label>
          <Input
            id="add-qty"
            aria-label="Quantity"
            inputMode="decimal"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
          />
        </div>

        {mode === 'part' ? (
          <div className="space-y-2">
            <Label htmlFor="add-markup">Markup %</Label>
            <Input
              id="add-markup"
              aria-label="Markup percent"
              inputMode="decimal"
              value={markupPct}
              onChange={(e) => setMarkupPct(e.target.value)}
              placeholder="Optional"
            />
          </div>
        ) : (
          <div className="space-y-2">
            <Label htmlFor="add-price">Unit price</Label>
            <Input
              id="add-price"
              aria-label="Unit price"
              inputMode="decimal"
              value={unitPrice}
              onChange={(e) => setUnitPrice(e.target.value)}
              placeholder="e.g. 100.00"
            />
          </div>
        )}
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

// ─── Main editor ────────────────────────────────────────────────────────────────

export function QuoteLineEditor({ quoteId, lines, isDraft }: QuoteLineEditorProps) {
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
              <TableHead className="text-right">Qty</TableHead>
              <TableHead className="text-right">Unit price</TableHead>
              <TableHead className="text-right">Markup %</TableHead>
              <TableHead className="text-right">Line total</TableHead>
              {isDraft && <TableHead className="text-right">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.map((line) => (
              <QuoteLineRow
                key={line.id}
                quoteId={quoteId}
                line={line}
                isDraft={isDraft}
                partName={partName}
              />
            ))}
          </TableBody>
        </Table>
      )}

      {isDraft && <AddLineForm quoteId={quoteId} />}
    </div>
  )
}
