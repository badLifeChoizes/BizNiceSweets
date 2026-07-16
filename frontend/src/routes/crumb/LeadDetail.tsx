// ABOUTME: CRUMB lead detail (/crumb/leads/:id) — an editable field card (name, company,
// ABOUTME: contact, source), the customer link + status summary, and the archive /
// ABOUTME: link-customer / convert-to-opportunity actions over /api/v1/crumb/leads/{id}.

/**
 * LeadDetail — single lead view (/crumb/leads/:id) (CRUMB-01).
 *
 * Layout: p-8 space-y-6, Back link → /crumb/leads.
 *
 * Data: useLead(id) → the lead; useCustomers() resolves partner_id → customer name.
 *
 * Editing: the four descriptive fields are edited inline and saved via useUpdateLead
 * (only the changed subset is PATCHed). Actions mirror the server FSM — Archive
 * (useArchiveLead, only while active), Link customer (dialog), Convert (dialog, which
 * navigates to the new opportunity). Every mutation toasts; a 4xx surfaces the reason.
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { CrumbNav } from './components/CrumbNav'
import { LeadStatusBadge } from './Leads'
import { LinkCustomerDialog } from './components/LinkCustomerDialog'
import { ConvertLeadDialog } from './components/ConvertLeadDialog'
import { useCustomers } from './components/lookups'
import { getApiErrorMessage } from './components/apiError'
import { useLead, useUpdateLead, useArchiveLead } from './hooks'

export function LeadDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [linkOpen, setLinkOpen] = useState(false)
  const [convertOpen, setConvertOpen] = useState(false)

  const { data: lead, isLoading, isError } = useLead(id)
  const { data: customers = [] } = useCustomers()

  // ── Editable field state (seeded from the loaded lead) ──
  const [name, setName] = useState('')
  const [company, setCompany] = useState('')
  const [contact, setContact] = useState('')
  const [source, setSource] = useState('')

  useEffect(() => {
    if (!lead) return
    setName(lead.name)
    setCompany(lead.company ?? '')
    setContact(lead.contact ?? '')
    setSource(lead.source ?? '')
  }, [lead])

  const updateMutation = useUpdateLead()
  const archiveMutation = useArchiveLead()

  function handleSave() {
    if (!lead) return
    updateMutation.mutate(
      {
        id: lead.id,
        patch: {
          name: name.trim(),
          company: company.trim() || null,
          contact: contact.trim() || null,
          source: source.trim() || null,
        },
      },
      {
        onSuccess: () => toast.success('Lead saved.'),
        onError: (err) =>
          toast.error(getApiErrorMessage(err, 'Failed to save the lead. Please try again.')),
      }
    )
  }

  function handleArchive() {
    if (!lead) return
    archiveMutation.mutate(lead.id, {
      onSuccess: () => toast.success('Lead archived.'),
      onError: (err) =>
        toast.error(getApiErrorMessage(err, 'Failed to archive the lead. Please try again.')),
    })
  }

  // ── Render: loading ──
  if (isLoading) {
    return (
      <div className="p-8 flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // ── Render: error ──
  if (isError || !lead) {
    return (
      <div className="p-8">
        <p className="text-sm text-muted-foreground">
          Could not load lead. Check your connection and try again.
        </p>
      </div>
    )
  }

  const customerName = lead.partner_id
    ? (customers.find((c) => c.id === lead.partner_id)?.name ?? lead.partner_id)
    : null
  const isSaving = updateMutation.isPending

  return (
    <div className="p-8 space-y-6">
      <CrumbNav />

      {/* Back navigation */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate('/crumb/leads')}
        className="flex items-center gap-1"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Back to Leads
      </Button>

      {/* Lead header card */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <p className="text-xl font-semibold text-foreground">{lead.name}</p>
                <LeadStatusBadge status={lead.status} />
                {!lead.active && (
                  <Badge variant="outline" className="text-muted-foreground">
                    Archived
                  </Badge>
                )}
              </div>
              <p className="text-base text-muted-foreground mt-0.5">
                {customerName ? `Customer: ${customerName}` : 'No customer linked'}
              </p>
            </div>
            {/* Actions */}
            <div className="flex items-center gap-2 shrink-0">
              <Button variant="outline" size="sm" onClick={() => setLinkOpen(true)}>
                Link Customer
              </Button>
              <Button variant="default" size="sm" onClick={() => setConvertOpen(true)}>
                Convert
              </Button>
              {lead.active && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleArchive}
                  disabled={archiveMutation.isPending}
                >
                  {archiveMutation.isPending ? (
                    <>
                      <Loader2 className="animate-spin" aria-hidden="true" />
                      Archiving…
                    </>
                  ) : (
                    'Archive'
                  )}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {lead.opportunity_id && (
            <Button
              variant="link"
              size="sm"
              className="px-0"
              onClick={() => navigate(`/crumb/opportunities/${lead.opportunity_id}`)}
            >
              View linked opportunity →
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Editable fields */}
      <Card>
        <CardHeader className="pb-2">
          <h2 className="text-base font-semibold text-foreground">Details</h2>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="detail-name">Name</Label>
              <Input
                id="detail-name"
                aria-label="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-company">Company</Label>
              <Input
                id="detail-company"
                aria-label="Company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-contact">Contact</Label>
              <Input
                id="detail-contact"
                aria-label="Contact"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-source">Source</Label>
              <Input
                id="detail-source"
                aria-label="Source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              />
            </div>
          </div>
          <div className="flex justify-end pt-4">
            <Button
              variant="default"
              onClick={handleSave}
              disabled={isSaving || name.trim() === ''}
            >
              {isSaving ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" />
                  Saving…
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Dialogs */}
      <LinkCustomerDialog leadId={lead.id} open={linkOpen} onOpenChange={setLinkOpen} />
      <ConvertLeadDialog
        leadId={lead.id}
        defaultName={lead.name}
        open={convertOpen}
        onOpenChange={setConvertOpen}
      />
    </div>
  )
}
