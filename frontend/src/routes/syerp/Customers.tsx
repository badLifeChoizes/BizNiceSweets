/**
 * Customers screen — SYERP customer master data list (/syerp/customers).
 *
 * Structural twin of Vendors.tsx. Differences:
 *   - role=customer query param and query key
 *   - Page heading: "Customers"
 *   - Search placeholder: "Search customers…"
 *   - Create button: "Create Customer"
 *   - aria-label: "Customer actions for {name}"
 *   - Copy throughout uses "customer" / "Customer"
 *
 * Layout: p-8 space-y-6 (matches Users.tsx and AppShell pattern).
 *
 * Toolbar:
 *   - Search Input (server-side, debounced 300ms via ?q= param)
 *   - Show archived Switch (wires to include_archived query param)
 *   - Create Customer Button (variant="default" — only accent element)
 *
 * Table columns: Name | Code | Contact | Country | Status | Actions
 *
 * Row actions (DropdownMenu):
 *   - Edit   → opens PartnerSheet (edit mode)
 *   - Archive → opens PartnerArchiveDialog (active rows only)
 *   - Restore → direct PATCH {active:true} + toast (archived rows only, no confirmation)
 *
 * Search: server-side via GET /api/v1/syerp/partners?role=customer&q={term}&include_archived={bool}
 * Query key: ['syerp', 'partners', 'customer', { q, includeArchived }]
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
import { PartnerSheet } from './components/PartnerSheet'
import { PartnerArchiveDialog } from './components/PartnerArchiveDialog'
import type { PartnerRead } from './components/PartnerSheet'

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchCustomers(q: string, includeArchived: boolean): Promise<PartnerRead[]> {
  const params = new URLSearchParams({ role: 'customer' })
  if (q) params.set('q', q)
  if (includeArchived) params.set('include_archived', 'true')
  return apiClient
    .get<PartnerRead[]>(`/api/v1/syerp/partners?${params.toString()}`)
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

export function Customers() {
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
  const [sheetPartner, setSheetPartner] = useState<PartnerRead | null>(null)

  // ── Archive dialog state ──
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [archivePartner, setArchivePartner] = useState<PartnerRead | null>(null)

  // ── Data ──
  const { data: customers = [], isLoading, isError } = useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'customer', { q: searchFilter, includeArchived }],
    queryFn: () => fetchCustomers(searchFilter, includeArchived),
  })

  // ── Restore mutation ──
  const restoreMutation = useMutation<PartnerRead, Error, string>({
    mutationFn: (partnerId) =>
      apiClient
        .patch<PartnerRead>(`/api/v1/syerp/partners/${partnerId}`, { active: true })
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'partners', 'customer'] })
      toast('Customer restored.')
    },
    onError: () => {
      toast.error('Failed to restore customer. Please try again.')
    },
  })

  // ── Handlers ──
  function openCreateSheet() {
    setSheetMode('create')
    setSheetPartner(null)
    setSheetOpen(true)
  }

  function openEditSheet(partner: PartnerRead) {
    setSheetMode('edit')
    setSheetPartner(partner)
    setSheetOpen(true)
  }

  function openArchiveDialog(partner: PartnerRead) {
    setArchivePartner(partner)
    setArchiveOpen(true)
  }

  function handleRestore(partner: PartnerRead) {
    restoreMutation.mutate(partner.id)
  }

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Customers</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manage customer master data.
        </p>
      </div>

      {/* Toolbar: Search + Show archived + Create Customer */}
      <div className="flex items-center gap-4">
        <Input
          placeholder="Search customers…"
          value={searchValue}
          onChange={handleSearchChange}
          className="max-w-xs"
          aria-label="Search customers"
        />
        <div className="flex items-center gap-2">
          <Switch
            id="customer-show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="customer-show-archived">Show archived</Label>
        </div>
        {/* "Create Customer" is the ONLY accent/default button on this screen */}
        <Button variant="default" onClick={openCreateSheet} className="ml-auto">
          Create Customer
        </Button>
      </div>

      {/* Customers table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load customers. Check your connection and refresh the page.
          </p>
        </div>
      ) : customers.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          {searchFilter ? (
            <>
              <p className="text-base font-semibold text-foreground">No customers found</p>
              <p className="text-sm text-muted-foreground">
                No customers match your search. Clear the filter or create a new customer.
              </p>
            </>
          ) : (
            <>
              <p className="text-base font-semibold text-foreground">No customers yet</p>
              <p className="text-sm text-muted-foreground">
                Add your first customer to get started.
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
              <TableHead>Contact</TableHead>
              <TableHead>Country</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {customers.map((customer) => (
              <TableRow key={customer.id} className="h-12">
                <TableCell className="font-medium">{customer.name}</TableCell>
                <TableCell>{customer.code}</TableCell>
                <TableCell>{customer.contact_name ?? '—'}</TableCell>
                <TableCell>{customer.addr_country ?? '—'}</TableCell>
                <TableCell>
                  <StatusBadge active={customer.active} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Customer actions for ${customer.name}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditSheet(customer)}>
                        Edit
                      </DropdownMenuItem>
                      {customer.active ? (
                        <DropdownMenuItem
                          onClick={() => openArchiveDialog(customer)}
                          className="text-destructive focus:text-destructive"
                        >
                          Archive
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => handleRestore(customer)}>
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
      <PartnerSheet
        open={sheetOpen}
        mode={sheetMode}
        partner={sheetPartner}
        role="customer"
        onClose={() => setSheetOpen(false)}
      />

      {/* ─── Archive Confirmation Dialog ──────────────────────────────────── */}
      <PartnerArchiveDialog
        open={archiveOpen}
        partner={archivePartner}
        role="customer"
        onClose={() => {
          setArchiveOpen(false)
          setArchivePartner(null)
        }}
      />
    </div>
  )
}
