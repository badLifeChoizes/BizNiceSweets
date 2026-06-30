/**
 * PriceBreakEditor — inline editable price-break row array.
 *
 * Props:
 *   rows: PriceBreakRow[] — current price-break data
 *   onChange: (rows: PriceBreakRow[]) => void — called on any row change
 *   disabled?: boolean — when true, all inputs and buttons are disabled
 *
 * Each row: qty_threshold (int min 1), unit_cost (decimal min 0), lead_days (int optional)
 * "Add Price Break" appends { qty_threshold: 1, unit_cost: 0, lead_days: null }
 * Trash2 ghost button removes the row at that index.
 *
 * Accessibility: each Input has aria-label including row index (1-based).
 */

import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Trash2, Plus } from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface PriceBreakRow {
  qty_threshold: number
  unit_cost: number
  lead_days: number | null
}

interface PriceBreakEditorProps {
  rows: PriceBreakRow[]
  onChange: (rows: PriceBreakRow[]) => void
  disabled?: boolean
}

// ─── Main component ──────────────────────────────────────────────────────────

export function PriceBreakEditor({ rows, onChange, disabled = false }: PriceBreakEditorProps) {
  function updateRow(index: number, field: keyof PriceBreakRow, rawValue: string) {
    const updated = rows.map((row, i) => {
      if (i !== index) return row
      if (field === 'lead_days') {
        const parsed = rawValue === '' ? null : parseInt(rawValue, 10)
        return { ...row, lead_days: isNaN(parsed as number) ? null : parsed }
      }
      if (field === 'qty_threshold') {
        return { ...row, qty_threshold: parseInt(rawValue, 10) || 1 }
      }
      if (field === 'unit_cost') {
        return { ...row, unit_cost: parseFloat(rawValue) || 0 }
      }
      return row
    })
    onChange(updated)
  }

  function removeRow(index: number) {
    onChange(rows.filter((_, i) => i !== index))
  }

  function addRow() {
    onChange([...rows, { qty_threshold: 1, unit_cost: 0, lead_days: null }])
  }

  return (
    <div>
      {rows.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Min Qty</TableHead>
              <TableHead>Unit Cost</TableHead>
              <TableHead>Lead Days</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, idx) => (
              <TableRow key={idx} className="h-10">
                <TableCell className="py-1">
                  <Input
                    type="number"
                    min="1"
                    value={row.qty_threshold}
                    onChange={(e) => updateRow(idx, 'qty_threshold', e.target.value)}
                    className="font-mono text-sm h-8 w-20"
                    aria-label={`Quantity threshold, row ${idx + 1}`}
                    disabled={disabled}
                  />
                </TableCell>
                <TableCell className="py-1">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={row.unit_cost}
                    onChange={(e) => updateRow(idx, 'unit_cost', e.target.value)}
                    className="font-mono text-sm h-8 w-24"
                    aria-label={`Unit cost, row ${idx + 1}`}
                    disabled={disabled}
                  />
                </TableCell>
                <TableCell className="py-1">
                  <Input
                    type="number"
                    min="0"
                    value={row.lead_days ?? ''}
                    onChange={(e) => updateRow(idx, 'lead_days', e.target.value)}
                    className="h-8 w-20"
                    placeholder="—"
                    aria-label={`Lead days, row ${idx + 1}`}
                    disabled={disabled}
                  />
                </TableCell>
                <TableCell className="py-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    type="button"
                    onClick={() => removeRow(idx)}
                    aria-label="Remove price break"
                    disabled={disabled}
                    className="h-8 w-8 p-0"
                  >
                    <Trash2 className="h-4 w-4 text-destructive" aria-hidden="true" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Button
        variant="ghost"
        size="sm"
        type="button"
        onClick={addRow}
        disabled={disabled}
        className="mt-2"
      >
        <Plus className="h-4 w-4 mr-1" aria-hidden="true" />
        Add Price Break
      </Button>
    </div>
  )
}
