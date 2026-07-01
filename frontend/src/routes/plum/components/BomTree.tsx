/**
 * BomTree — recursive expandable BOM tree and flat BOM table for Part Detail.
 *
 * Props:
 *   partId: string
 *   revisionId: string — current revision; BOM is fetched for this revision
 *   isDraft: boolean — shows edit actions only when true (D-01 immutability)
 *   onEdit?: (line: BomTreeNode) => void — called when user clicks "Edit Line"
 *   onRemove?: (line: BomTreeNode) => void — called when user clicks "Remove"
 *
 * Views (PLUM-04 / PLUM-05):
 *   tree: recursive <ul> with expand/collapse (default; all expanded on load)
 *   flat: <Table> with total qty roll-up (GET /bom/flat endpoint)
 *
 * Query keys:
 *   ['plum', 'parts', partId, 'bom', revisionId] — tree view
 *   ['plum', 'parts', partId, 'bom', 'flat'] — flat view
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Loader2 } from 'lucide-react'
import { apiClient } from '@/api/client'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MoreHorizontal } from 'lucide-react'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface BomTreeNode {
  bom_item_id: string
  child_part_id: string
  child_part_number: string
  child_revision_label?: string | null
  child_revision_status?: string | null
  quantity: number | string
  reference_designators?: string | null
  effective_cost?: number | string | null
  effective_cost_source?: string | null
  is_unreleased?: boolean
  unit_of_measure?: string | null
  description?: string | null
  children?: BomTreeNode[]
}

interface FlatBomRow {
  child_part_id: string
  part_number: string
  description?: string | null
  total_qty: number | string
  unit_of_measure?: string | null
  effective_cost?: number | string | null
  extended_cost?: number | string | null
}

interface BomTreeProps {
  partId: string
  revisionId: string
  isDraft: boolean
  onEdit?: (line: BomTreeNode) => void
  onRemove?: (line: BomTreeNode) => void
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function collectAllIds(nodes: BomTreeNode[]): Set<string> {
  const ids = new Set<string>()
  function walk(items: BomTreeNode[]) {
    for (const item of items) {
      ids.add(item.bom_item_id)
      if (item.children?.length) walk(item.children)
    }
  }
  walk(nodes)
  return ids
}

function formatCost(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  return num.toFixed(4)
}

// ─── BomRow — recursive row ───────────────────────────────────────────────────

interface BomRowProps {
  item: BomTreeNode
  depth: number
  isDraft: boolean
  expandedIds: Set<string>
  onToggle: (id: string) => void
  onEdit?: (line: BomTreeNode) => void
  onRemove?: (line: BomTreeNode) => void
}

function BomRow({ item, depth, isDraft, expandedIds, onToggle, onEdit, onRemove }: BomRowProps) {
  const hasChildren = (item.children?.length ?? 0) > 0
  const isExpanded = expandedIds.has(item.bom_item_id)

  const refDes = item.reference_designators ?? ''
  const truncatedRefDes = refDes.length > 48 ? refDes.substring(0, 48) + '…' : refDes

  return (
    <li role="treeitem" aria-expanded={hasChildren ? isExpanded : undefined}>
      <div
        className="flex items-center gap-2 py-1 pr-2 hover:bg-muted/30 rounded-sm"
        style={{ paddingLeft: `${depth * 24 + 4}px` }}
      >
        {/* expand/collapse toggle */}
        {hasChildren ? (
          <button
            type="button"
            onClick={() => onToggle(item.bom_item_id)}
            aria-expanded={isExpanded}
            aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${item.child_part_number}`}
            className="flex-none text-muted-foreground hover:text-foreground"
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            ) : (
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        ) : (
          <span className="flex-none w-4" />
        )}

        {/* part number with tooltip for description */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="font-medium text-sm text-foreground cursor-default">
                {item.child_part_number}
              </span>
            </TooltipTrigger>
            {item.description && (
              <TooltipContent>
                <p>{item.description}</p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>

        {/* revision label */}
        {item.child_revision_label && (
          <span className="text-xs text-muted-foreground">{item.child_revision_label}</span>
        )}

        {/* unreleased badge */}
        {item.is_unreleased && (
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-amber-50 text-amber-700"
            title="No Released revision — using latest Draft"
          >
            Unreleased
          </span>
        )}

        {/* quantity + UoM */}
        <span className="font-mono text-sm text-foreground ml-auto">
          {item.quantity}
          {item.unit_of_measure && (
            <span className="text-muted-foreground ml-1">{item.unit_of_measure}</span>
          )}
        </span>

        {/* reference designators */}
        {truncatedRefDes && (
          <span className="text-xs text-muted-foreground" title={refDes}>
            {truncatedRefDes}
          </span>
        )}

        {/* effective cost */}
        <span className="font-mono text-sm w-20 text-right">
          {item.effective_cost !== null && item.effective_cost !== undefined
            ? <span className="text-foreground">{formatCost(item.effective_cost)}</span>
            : <span className="text-muted-foreground">—</span>
          }
        </span>

        {/* row actions (Draft only) */}
        {isDraft && (onEdit || onRemove) && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-11 w-11"
                aria-label={`Actions for ${item.child_part_number}`}
              >
                <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {onEdit && (
                <DropdownMenuItem onClick={() => onEdit(item)}>
                  Edit Line
                </DropdownMenuItem>
              )}
              {onRemove && (
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => onRemove(item)}
                >
                  Remove
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* children (recursive) */}
      {isExpanded && hasChildren && (
        <ul role="group">
          {item.children!.map((child) => (
            <BomRow
              key={child.bom_item_id}
              item={child}
              depth={depth + 1}
              isDraft={isDraft}
              expandedIds={expandedIds}
              onToggle={onToggle}
              onEdit={onEdit}
              onRemove={onRemove}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function BomTree({ partId, revisionId, isDraft, onEdit, onRemove }: BomTreeProps) {
  const [viewMode, setViewMode] = useState<'tree' | 'flat'>('tree')
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [initialized, setInitialized] = useState(false)

  // ── Tree query ──
  const {
    data: treeData,
    isLoading: treeLoading,
    isError: treeError,
  } = useQuery<{ items?: BomTreeNode[]; children?: BomTreeNode[] } | BomTreeNode[], Error>({
    queryKey: ['plum', 'parts', partId, 'bom', revisionId],
    queryFn: () =>
      apiClient
        .get<{ items?: BomTreeNode[]; children?: BomTreeNode[] } | BomTreeNode[]>(
          `/api/v1/plum/parts/${partId}/bom`,
          { params: { rev_id: revisionId } },
        )
        .then((r) => r.data),
    enabled: !!partId && !!revisionId,
  })

  // ── Flat query (only fetch when in flat mode) ──
  const {
    data: flatData,
    isLoading: flatLoading,
  } = useQuery<FlatBomRow[], Error>({
    queryKey: ['plum', 'parts', partId, 'bom', 'flat'],
    queryFn: () =>
      apiClient
        .get<FlatBomRow[]>(`/api/v1/plum/parts/${partId}/bom/flat`, {
          params: { rev_id: revisionId },
        })
        .then((r) => r.data),
    enabled: !!partId && !!revisionId && viewMode === 'flat',
  })

  // ── Normalize tree nodes from API response ──
  function getTreeNodes(): BomTreeNode[] {
    if (!treeData) return []
    if (Array.isArray(treeData)) return treeData
    // Handles { items: [...] } or { children: [...] } shapes
    if ((treeData as { items?: BomTreeNode[] }).items) {
      return (treeData as { items: BomTreeNode[] }).items
    }
    if ((treeData as { children?: BomTreeNode[] }).children) {
      return (treeData as { children: BomTreeNode[] }).children
    }
    return []
  }

  const treeNodes = getTreeNodes()

  // ── Initialize expanded state (all expanded on first load) ──
  useEffect(() => {
    if (!initialized && treeNodes.length > 0) {
      setExpandedIds(collectAllIds(treeNodes))
      setInitialized(true)
    }
  }, [treeNodes, initialized])

  function toggleNode(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  // ── Compute flat BOM total ──
  const flatRows = flatData ?? []
  const totalBomCost = flatRows.reduce((sum, row) => {
    const ec = row.extended_cost
    if (ec === null || ec === undefined || ec === '') return sum
    const num = typeof ec === 'string' ? parseFloat(ec) : ec
    return isNaN(num) ? sum : sum + num
  }, 0)

  // ── Render ──
  return (
    <div>
      {/* Tree / Flat view toggle */}
      <div className="flex gap-1 border-b border-border mb-4">
        <button
          type="button"
          className={
            viewMode === 'tree'
              ? 'pb-2 border-b-2 border-primary text-foreground text-sm font-medium'
              : 'pb-2 border-b-2 border-transparent text-muted-foreground text-sm'
          }
          onClick={() => setViewMode('tree')}
        >
          Tree
        </button>
        <button
          type="button"
          className={
            viewMode === 'flat'
              ? 'pb-2 border-b-2 border-primary text-foreground text-sm font-medium'
              : 'pb-2 border-b-2 border-transparent text-muted-foreground text-sm'
          }
          onClick={() => setViewMode('flat')}
        >
          Flat
        </button>
      </div>

      {/* Tree view */}
      {viewMode === 'tree' && (
        <>
          {treeLoading && (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {treeError && (
            <p className="text-sm text-muted-foreground text-center py-6">
              Could not load BOM. Please try again.
            </p>
          )}
          {!treeLoading && !treeError && treeNodes.length === 0 && (
            <>
              <p className="text-sm text-muted-foreground text-center py-6">
                No parts added yet.
              </p>
              <p className="text-xs text-muted-foreground text-center">
                Add child parts to build a bill of materials for this revision.
              </p>
            </>
          )}
          {!treeLoading && !treeError && treeNodes.length > 0 && (
            <ul role="tree" aria-label="Bill of Materials">
              {treeNodes.map((node) => (
                <BomRow
                  key={node.bom_item_id}
                  item={node}
                  depth={0}
                  isDraft={isDraft}
                  expandedIds={expandedIds}
                  onToggle={toggleNode}
                  onEdit={onEdit}
                  onRemove={onRemove}
                />
              ))}
            </ul>
          )}
        </>
      )}

      {/* Flat view */}
      {viewMode === 'flat' && (
        <>
          {flatLoading && (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {!flatLoading && flatRows.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">
              No parts added yet.
            </p>
          )}
          {!flatLoading && flatRows.length > 0 && (
            <Table aria-label="Flat bill of materials">
              <TableHeader>
                <TableRow>
                  <TableHead>Part Number</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Total Qty</TableHead>
                  <TableHead>UoM</TableHead>
                  <TableHead className="text-right">Effective Cost</TableHead>
                  <TableHead className="text-right">Extended Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {flatRows.map((row) => (
                  <TableRow key={row.child_part_id}>
                    <TableCell className="font-medium">{row.part_number}</TableCell>
                    <TableCell className="text-muted-foreground">{row.description ?? '—'}</TableCell>
                    <TableCell className="font-mono text-right">{row.total_qty}</TableCell>
                    <TableCell>{row.unit_of_measure ?? '—'}</TableCell>
                    <TableCell className="font-mono text-right">
                      {formatCost(row.effective_cost)}
                    </TableCell>
                    <TableCell className="font-mono text-right">
                      {formatCost(row.extended_cost)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              {/* Total BOM Cost footer */}
              <tfoot>
                <tr className="border-t border-border">
                  <td colSpan={5} className="px-4 py-3 text-sm font-semibold text-foreground">
                    Total BOM Cost
                  </td>
                  <td className="px-4 py-3 font-semibold font-mono text-right text-sm text-foreground">
                    {totalBomCost > 0 ? totalBomCost.toFixed(4) : '—'}
                  </td>
                </tr>
              </tfoot>
            </Table>
          )}
        </>
      )}
    </div>
  )
}
