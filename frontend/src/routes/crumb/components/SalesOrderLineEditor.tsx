// ABOUTME: Sales-order create-line editor (CRUMB-01, Phase 11b) — builds the ordered lines
// ABOUTME: for a not-yet-persisted draft SO in local state (PLUM-part or free-text, each with
// ABOUTME: qty + unit price). Controlled: parent holds the lines array; on submit they POST.

/**
 * SalesOrderLineEditor — the ordered-line grid inside the "New sales order" dialog.
 *
 * Unlike QuoteLineEditor (which mutates persisted lines on the detail screen), the SO
 * does not exist yet at create time, so this editor is a controlled local-state builder:
 * the parent owns `lines` (SalesOrderLinePayload[]) and receives every add/remove via
 * `onChange`; the whole array is submitted with the create request.
 *
 * Add form toggles between:
 *   - PLUM part: pick a part + qty + unit price. plum_part_id is sent; the label resolves
 *     to the part number for display.
 *   - Free text: description + qty + unit price.
 *
 * Both variants require an explicit unit_price (SalesOrderLineCreate.unit_price is required).
 * No line/grand total is computed here — money & qty are Decimal-as-string (D-11) and the
 * server derives line_total after creation, so we never do float math on them.
 */

import { useState } from 'react'
import { Trash2 } from 'lucide-react'
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
import type { SalesOrderLinePayload } from '../hooks'
import { usePlumParts } from './lookups'

interface SalesOrderLineEditorProps {
  lines: SalesOrderLinePayload[]
  onChange: (lines: SalesOrderLinePayload[]) => void
}

// A qty string parsed for a decimal-safe ">0" test. Blank / non-numeric → 0.
function toNumber(value: string): number {
  const n = Number(value)
  if (value.trim() === '' || !Number.isFinite(n)) return 0
  return n
}

type AddMode = 'part' | 'free'

export function SalesOrderLineEditor({ lines, onChange }: SalesOrderLineEditorProps) {
  const { data: parts = [] } = usePlumParts()
  const partName = (id: string | null | undefined) =>
    parts.find((p) => p.id === id)?.part_number ?? id ?? '—'

  const [mode, setMode] = useState<AddMode>('part')
  const [partId, setPartId] = useState('')
  const [description, setDescription] = useState('')
  const [qtyOrdered, setQtyOrdered] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')

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
    const line: SalesOrderLinePayload =
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
    onChange([...lines, line])
    reset()
  }

  function handleRemove(index: number) {
    onChange(lines.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-4">
      {lines.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-4">
          No lines yet — add a PLUM-part or free-text line below.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead className="text-right">Qty</TableHead>
              <TableHead className="text-right">Unit price</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {lines.map((line, index) => (
              <TableRow key={index} className="h-12">
                <TableCell className="font-medium">
                  {line.plum_part_id ? partName(line.plum_part_id) : (line.description ?? '—')}
                </TableCell>
                <TableCell className="text-right font-mono">{line.qty_ordered}</TableCell>
                <TableCell className="text-right font-mono">{line.unit_price}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemove(index)}
                    aria-label="Remove line"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Add-line form */}
      <div className="space-y-4 rounded-md border border-border p-4">
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
              <Label htmlFor="so-add-part">Part</Label>
              <Select value={partId} onValueChange={setPartId}>
                <SelectTrigger id="so-add-part" aria-label="Part">
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
              <Label htmlFor="so-add-description">Description</Label>
              <Input
                id="so-add-description"
                aria-label="Description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Installation service"
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="so-add-qty">Quantity</Label>
            <Input
              id="so-add-qty"
              aria-label="Quantity"
              inputMode="decimal"
              value={qtyOrdered}
              onChange={(e) => setQtyOrdered(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="so-add-price">Unit price</Label>
            <Input
              id="so-add-price"
              aria-label="Unit price"
              inputMode="decimal"
              value={unitPrice}
              onChange={(e) => setUnitPrice(e.target.value)}
              placeholder="e.g. 100.00"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <Button variant="default" size="sm" onClick={handleAdd} disabled={!canAdd}>
            Add Line
          </Button>
        </div>
      </div>
    </div>
  )
}
