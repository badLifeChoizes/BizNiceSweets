// ABOUTME: CRUMB Leads list screen (/crumb/leads) — a table of leads (name, company,
// ABOUTME: status), a "New lead" create dialog and a show-archived toggle over
// ABOUTME: /api/v1/crumb/leads. Rows navigate to the lead detail sheet (CRUMB-01).

/**
 * Leads screen — the CRUMB lead list (/crumb/leads).
 *
 * Layout: p-8 space-y-6 (matches the MOUSSE WorkOrders / SYERP list pattern).
 *
 * Table columns: Name | Company | Status
 *
 * The show-archived toggle flips useLeads(includeArchived); archived rows carry an
 * extra "Archived" badge so soft-deleted leads read differently from live ones. Row
 * click navigates to /crumb/leads/{id} (the detail screen).
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
import { CrumbNav } from './components/CrumbNav'
import { LeadCreateDialog } from './components/LeadCreateDialog'
import { useLeads } from './hooks'

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Lead status → Badge variant + label. Color AND text together (never color alone). */
export function LeadStatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: 'default' | 'secondary' | 'outline'; className?: string; label: string }
  > = {
    new: { variant: 'secondary', label: 'New' },
    qualified: {
      variant: 'outline',
      className: 'border-blue-300 bg-blue-50 text-blue-700',
      label: 'Qualified',
    },
    converted: {
      variant: 'outline',
      className: 'border-green-300 bg-green-50 text-green-700',
      label: 'Converted',
    },
  }
  const cfg = map[status] ?? { variant: 'secondary' as const, label: status }
  return (
    <Badge variant={cfg.variant} className={cfg.className}>
      {cfg.label}
    </Badge>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Leads() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [includeArchived, setIncludeArchived] = useState(false)

  const { data: leads = [], isLoading, isError } = useLeads(includeArchived)

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Leads</h1>
        <p className="text-base font-normal text-muted-foreground">
          Capture prospects, link them to SYERP customers, and convert qualified leads
          into pipeline opportunities.
        </p>
      </div>

      {/* Toolbar: show-archived toggle + create */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Switch
            id="show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="show-archived" className="text-sm text-muted-foreground">
            Show archived
          </Label>
        </div>
        <Button variant="default" className="ml-auto" onClick={() => setCreateOpen(true)}>
          New Lead
        </Button>
      </div>

      {/* Leads table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load leads. Check your connection and refresh the page.
          </p>
        </div>
      ) : leads.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No leads yet</p>
          <p className="text-sm text-muted-foreground">
            Create your first lead to get started.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.map((lead) => (
              <TableRow
                key={lead.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/crumb/leads/${lead.id}`)}
                aria-label={`View lead ${lead.name}`}
              >
                <TableCell className="font-medium">{lead.name}</TableCell>
                <TableCell>{lead.company ?? '—'}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <LeadStatusBadge status={lead.status} />
                    {!lead.active && (
                      <Badge variant="outline" className="text-muted-foreground">
                        Archived
                      </Badge>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Create dialog */}
      <LeadCreateDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  )
}
