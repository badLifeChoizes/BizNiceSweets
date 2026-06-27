/**
 * PartnerSheet — shared create/edit form for vendor and customer partners.
 *
 * Props:
 *   open: boolean — controls sheet visibility
 *   mode: 'create' | 'edit' — determines title, description, and mutation used
 *   partner: PartnerRead | null — pre-populated for edit mode
 *   role: 'vendor' | 'customer' — determines which role Switch is pre-checked on create
 *   onClose: () => void — called on Save success or Discard
 *
 * Sections (Separator-divided):
 *   1. Identity  — Name, Code, Is Vendor, Is Customer
 *   2. Address   — Line 1/2, City, State, Postal, Country
 *   3. Contact   — Name, Email, Phone
 *   4. Commerce  — Payment Terms, Tax ID, Currency, Country of Origin, Notes
 *
 * Role validation: at least one of Is Vendor / Is Customer must be on.
 * Currency default: read from GET /api/v1/core/settings default_currency on create mount.
 *
 * Mutations:
 *   Create: POST /api/v1/syerp/partners — onSuccess invalidate ['syerp','partners',role]
 *   Edit:   PATCH /api/v1/syerp/partners/{id} — onSuccess invalidate ['syerp','partners',role]
 *
 * Accessibility: every input has a paired Label; Sheet has aria-labelledby + aria-describedby.
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { apiClient } from '@/api/client'
import { cn } from '@/lib/utils'
import type { SettingRecord } from '@/hooks/useSettings'

// ─── Types ───────────────────────────────────────────────────────────────────

export interface PartnerRead {
  id: string
  code: string
  name: string
  is_vendor: boolean
  is_customer: boolean
  active: boolean
  addr_line1?: string | null
  addr_line2?: string | null
  addr_city?: string | null
  addr_state?: string | null
  addr_postal?: string | null
  addr_country?: string | null
  contact_name?: string | null
  contact_email?: string | null
  contact_phone?: string | null
  payment_terms?: string | null
  tax_id?: string | null
  currency?: string | null
  country_of_origin?: string | null
  notes?: string | null
  created_at: string
  updated_at: string
}

interface PartnerSheetProps {
  open: boolean
  mode: 'create' | 'edit'
  partner: PartnerRead | null
  role: 'vendor' | 'customer'
  onClose: () => void
}

// ─── Currency options (mirrored from Settings.tsx) ────────────────────────────

const CURRENCY_OPTIONS = [
  { value: 'USD', label: 'USD — US Dollar' },
  { value: 'EUR', label: 'EUR — Euro' },
  { value: 'GBP', label: 'GBP — British Pound' },
  { value: 'JPY', label: 'JPY — Japanese Yen' },
  { value: 'CAD', label: 'CAD — Canadian Dollar' },
  { value: 'AUD', label: 'AUD — Australian Dollar' },
]

const PAYMENT_TERMS_OPTIONS = [
  { value: 'Net 30', label: 'Net 30' },
  { value: 'Net 60', label: 'Net 60' },
  { value: 'Net 90', label: 'Net 90' },
  { value: 'Due on Receipt', label: 'Due on Receipt' },
  { value: 'Prepaid', label: 'Prepaid' },
]

// ─── API error helper ─────────────────────────────────────────────────────────
// Surface the server's real reason instead of a generic "please try again".
// FastAPI returns either a string `detail` (e.g. 409 duplicate code) or a
// 422 validation array of { loc, msg }. Map both to a readable, actionable message.
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

// ─── Main component ──────────────────────────────────────────────────────────

export function PartnerSheet({ open, mode, partner, role, onClose }: PartnerSheetProps) {
  const queryClient = useQueryClient()

  // ── Settings fetch for currency default ──
  const { data: settings = [] } = useQuery<SettingRecord[], Error>({
    queryKey: ['core', 'settings'],
    queryFn: () =>
      apiClient.get<SettingRecord[]>('/api/v1/core/settings').then((r) => r.data),
    staleTime: 5 * 60 * 1000, // 5 min — cache hit from AppShell chain
  })

  function getDefaultCurrency(): string {
    const rec = settings.find((s) => s.key === 'locale.currency')
    return rec?.value ?? 'USD'
  }

  // ── Form state ──
  const [formName, setFormName] = useState('')
  const [formCode, setFormCode] = useState('')
  const [formIsVendor, setFormIsVendor] = useState(false)
  const [formIsCustomer, setFormIsCustomer] = useState(false)

  const [formAddrLine1, setFormAddrLine1] = useState('')
  const [formAddrLine2, setFormAddrLine2] = useState('')
  const [formAddrCity, setFormAddrCity] = useState('')
  const [formAddrState, setFormAddrState] = useState('')
  const [formAddrPostal, setFormAddrPostal] = useState('')
  const [formAddrCountry, setFormAddrCountry] = useState('')

  const [formContactName, setFormContactName] = useState('')
  const [formContactEmail, setFormContactEmail] = useState('')
  const [formContactPhone, setFormContactPhone] = useState('')

  const [formPaymentTerms, setFormPaymentTerms] = useState('')
  const [formTaxId, setFormTaxId] = useState('')
  const [formCurrency, setFormCurrency] = useState('USD')
  const [formCountryOfOrigin, setFormCountryOfOrigin] = useState('')
  const [formNotes, setFormNotes] = useState('')

  // ── Populate form when sheet opens ──
  useEffect(() => {
    if (!open) return

    if (mode === 'create') {
      setFormName('')
      setFormCode('')
      setFormIsVendor(role === 'vendor')
      setFormIsCustomer(role === 'customer')
      setFormAddrLine1('')
      setFormAddrLine2('')
      setFormAddrCity('')
      setFormAddrState('')
      setFormAddrPostal('')
      setFormAddrCountry('')
      setFormContactName('')
      setFormContactEmail('')
      setFormContactPhone('')
      setFormPaymentTerms('')
      setFormTaxId('')
      setFormCurrency(getDefaultCurrency())
      setFormCountryOfOrigin('')
      setFormNotes('')
    } else if (mode === 'edit' && partner) {
      setFormName(partner.name)
      setFormCode(partner.code)
      setFormIsVendor(partner.is_vendor)
      setFormIsCustomer(partner.is_customer)
      setFormAddrLine1(partner.addr_line1 ?? '')
      setFormAddrLine2(partner.addr_line2 ?? '')
      setFormAddrCity(partner.addr_city ?? '')
      setFormAddrState(partner.addr_state ?? '')
      setFormAddrPostal(partner.addr_postal ?? '')
      setFormAddrCountry(partner.addr_country ?? '')
      setFormContactName(partner.contact_name ?? '')
      setFormContactEmail(partner.contact_email ?? '')
      setFormContactPhone(partner.contact_phone ?? '')
      setFormPaymentTerms(partner.payment_terms ?? '')
      setFormTaxId(partner.tax_id ?? '')
      setFormCurrency(partner.currency ?? getDefaultCurrency())
      setFormCountryOfOrigin(partner.country_of_origin ?? '')
      setFormNotes(partner.notes ?? '')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, partner, role])

  // ── Role validation ──
  const roleError = !formIsVendor && !formIsCustomer

  // ── Mutations ──
  interface PartnerPayload {
    name: string
    code?: string
    is_vendor: boolean
    is_customer: boolean
    addr_line1?: string
    addr_line2?: string
    addr_city?: string
    addr_state?: string
    addr_postal?: string
    addr_country?: string
    contact_name?: string
    contact_email?: string
    contact_phone?: string
    payment_terms?: string
    tax_id?: string
    currency?: string
    country_of_origin?: string
    notes?: string
  }

  function buildPayload(): PartnerPayload {
    return {
      name: formName,
      code: formCode || undefined,
      is_vendor: formIsVendor,
      is_customer: formIsCustomer,
      addr_line1: formAddrLine1 || undefined,
      addr_line2: formAddrLine2 || undefined,
      addr_city: formAddrCity || undefined,
      addr_state: formAddrState || undefined,
      addr_postal: formAddrPostal || undefined,
      addr_country: formAddrCountry || undefined,
      contact_name: formContactName || undefined,
      contact_email: formContactEmail || undefined,
      contact_phone: formContactPhone || undefined,
      payment_terms: formPaymentTerms || undefined,
      tax_id: formTaxId || undefined,
      currency: formCurrency || undefined,
      country_of_origin: formCountryOfOrigin || undefined,
      notes: formNotes || undefined,
    }
  }

  const createMutation = useMutation<PartnerRead, Error, PartnerPayload>({
    mutationFn: (payload) =>
      apiClient.post<PartnerRead>('/api/v1/syerp/partners', payload).then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'partners', role] })
      toast(role === 'vendor' ? 'Vendor saved.' : 'Customer saved.')
      onClose()
    },
    onError: (err) => {
      toast.error(
        getApiErrorMessage(
          err,
          role === 'vendor'
            ? 'Failed to save vendor. Please try again.'
            : 'Failed to save customer. Please try again.',
        ),
      )
    },
  })

  const updateMutation = useMutation<PartnerRead, Error, PartnerPayload>({
    mutationFn: (payload) =>
      apiClient
        .patch<PartnerRead>(`/api/v1/syerp/partners/${partner?.id}`, payload)
        .then((r) => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['syerp', 'partners', role] })
      toast(role === 'vendor' ? 'Vendor saved.' : 'Customer saved.')
      onClose()
    },
    onError: (err) => {
      toast.error(
        getApiErrorMessage(
          err,
          role === 'vendor'
            ? 'Failed to save vendor. Please try again.'
            : 'Failed to save customer. Please try again.',
        ),
      )
    },
  })

  const isSaving = createMutation.isPending || updateMutation.isPending

  function handleSave() {
    if (roleError) return
    const payload = buildPayload()
    if (mode === 'create') {
      createMutation.mutate(payload)
    } else {
      updateMutation.mutate(payload)
    }
  }

  function handleOpenChange(isOpen: boolean) {
    if (!isOpen) onClose()
  }

  // ── Sheet title / description ──
  function getSheetTitle() {
    if (mode === 'edit') return 'Edit Partner'
    return role === 'vendor' ? 'Create Vendor' : 'Create Customer'
  }

  function getSheetDescription() {
    if (mode === 'edit') return 'Update the partner record. Changes are audited.'
    return role === 'vendor'
      ? 'Fill in the details to add a new vendor.'
      : 'Fill in the details to add a new customer.'
  }

  // ── Render ──
  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent
        side="right"
        aria-labelledby="partner-sheet-title"
        aria-describedby="partner-sheet-description"
        className="overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle id="partner-sheet-title">{getSheetTitle()}</SheetTitle>
          <SheetDescription id="partner-sheet-description">
            {getSheetDescription()}
          </SheetDescription>
        </SheetHeader>

        <div className="py-6 space-y-6">
          {/* ─── Section 1: Identity ─────────────────────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="partner-name">Name</Label>
              <Input
                id="partner-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-code">Code</Label>
              <Input
                id="partner-code"
                value={formCode}
                onChange={(e) => setFormCode(e.target.value)}
                placeholder="P-0001"
              />
            </div>

            {/* Is Vendor switch */}
            <div className="flex items-center gap-3">
              <Switch
                id="partner-is-vendor"
                checked={formIsVendor}
                onCheckedChange={setFormIsVendor}
              />
              <Label htmlFor="partner-is-vendor">This partner is a vendor</Label>
            </div>

            {/* Is Customer switch */}
            <div className="flex items-center gap-3">
              <Switch
                id="partner-is-customer"
                checked={formIsCustomer}
                onCheckedChange={setFormIsCustomer}
              />
              <Label htmlFor="partner-is-customer">This partner is a customer</Label>
            </div>

            {/* Role validation error */}
            {roleError && (
              <p className="text-sm text-destructive">At least one role must be selected.</p>
            )}
          </div>

          <Separator />

          {/* ─── Section 2: Address ──────────────────────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="partner-addr-line1">Address Line 1</Label>
              <Input
                id="partner-addr-line1"
                value={formAddrLine1}
                onChange={(e) => setFormAddrLine1(e.target.value)}
                placeholder="123 Main St"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-addr-line2">Address Line 2</Label>
              <Input
                id="partner-addr-line2"
                value={formAddrLine2}
                onChange={(e) => setFormAddrLine2(e.target.value)}
                placeholder="Suite 400"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-addr-city">City</Label>
              <Input
                id="partner-addr-city"
                value={formAddrCity}
                onChange={(e) => setFormAddrCity(e.target.value)}
                placeholder="Springfield"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-addr-state">State / Region</Label>
              <Input
                id="partner-addr-state"
                value={formAddrState}
                onChange={(e) => setFormAddrState(e.target.value)}
                placeholder="IL"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-addr-postal">Postal Code</Label>
              <Input
                id="partner-addr-postal"
                value={formAddrPostal}
                onChange={(e) => setFormAddrPostal(e.target.value)}
                placeholder="62701"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-addr-country">Country</Label>
              <Input
                id="partner-addr-country"
                value={formAddrCountry}
                onChange={(e) => setFormAddrCountry(e.target.value.toUpperCase().slice(0, 2))}
                maxLength={2}
                placeholder="US"
              />
              <p className="text-xs text-muted-foreground">
                2-letter country code (ISO 3166), e.g. US, GB, DE.
              </p>
            </div>
          </div>

          <Separator />

          {/* ─── Section 3: Contact ──────────────────────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="partner-contact-name">Contact Name</Label>
              <Input
                id="partner-contact-name"
                value={formContactName}
                onChange={(e) => setFormContactName(e.target.value)}
                placeholder="Jane Smith"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-contact-email">Email</Label>
              <Input
                id="partner-contact-email"
                type="email"
                value={formContactEmail}
                onChange={(e) => setFormContactEmail(e.target.value)}
                placeholder="jane@acme.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-contact-phone">Phone</Label>
              <Input
                id="partner-contact-phone"
                value={formContactPhone}
                onChange={(e) => setFormContactPhone(e.target.value)}
                placeholder="+1 (555) 000-0000"
              />
            </div>
          </div>

          <Separator />

          {/* ─── Section 4: Commerce ─────────────────────────────────────── */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="partner-payment-terms">Payment Terms</Label>
              <Select value={formPaymentTerms} onValueChange={setFormPaymentTerms}>
                <SelectTrigger id="partner-payment-terms">
                  <SelectValue placeholder="Select payment terms" />
                </SelectTrigger>
                <SelectContent>
                  {PAYMENT_TERMS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-tax-id">Tax ID (EIN/VAT)</Label>
              <Input
                id="partner-tax-id"
                value={formTaxId}
                onChange={(e) => setFormTaxId(e.target.value)}
                placeholder="12-3456789"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-currency">Currency</Label>
              <Select value={formCurrency} onValueChange={setFormCurrency}>
                <SelectTrigger id="partner-currency">
                  <SelectValue placeholder="Select currency" />
                </SelectTrigger>
                <SelectContent>
                  {CURRENCY_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-country-of-origin">Country of Origin</Label>
              <Input
                id="partner-country-of-origin"
                value={formCountryOfOrigin}
                onChange={(e) => setFormCountryOfOrigin(e.target.value.toUpperCase().slice(0, 2))}
                maxLength={2}
                placeholder="US"
              />
              <p className="text-xs text-muted-foreground">
                2-letter country code (ISO 3166), e.g. US, GB, DE.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="partner-notes">Notes</Label>
              <textarea
                id="partner-notes"
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="Optional notes…"
                rows={3}
                className={cn(
                  'flex w-full rounded-md border border-input bg-transparent px-3 py-2',
                  'text-base shadow-sm placeholder:text-muted-foreground',
                  'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
                  'disabled:cursor-not-allowed disabled:opacity-50',
                )}
              />
            </div>
          </div>
        </div>

        <SheetFooter className={cn('flex gap-2 pt-4')}>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Discard Changes
          </Button>
          <Button
            variant="default"
            onClick={handleSave}
            disabled={isSaving || roleError}
          >
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Saving…
              </>
            ) : (
              'Save Partner'
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
