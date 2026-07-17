// ABOUTME: CRUMB (CRM) TanStack Query hooks + shared request/response types. Wraps the
// ABOUTME: /api/v1/crumb/* API (leads, opportunities, quotes+lines, interactions) through
// ABOUTME: the single axios client. Money fields arrive as exact STRINGS (D-11) — render
// ABOUTME: as-is, never float math.

/**
 * CRUMB pipeline hooks — the query seam shared by the Leads, Pipeline, Quotes and
 * Communications screens (CRUMB-01).
 *
 * Query keys (kept in one place so mutations can invalidate consistently):
 *   ['crumb', 'leads']                  — the lead list
 *   ['crumb', 'leads', id]              — one lead's detail
 *   ['crumb', 'opportunities']          — the opportunity list
 *   ['crumb', 'pipeline']               — the stage-grouped board (?pipeline=true)
 *   ['crumb', 'quotes']                 — the quote-header list
 *   ['crumb', 'quotes', id]             — one quote's detail (header + priced lines)
 *   ['crumb', 'sales-orders']           — the sales-order header list
 *   ['crumb', 'sales-orders', id]       — one sales order's detail (header + lines)
 *   ['crumb', 'interactions', partnerId]— a customer's interaction timeline
 *
 * Reads are GETs; every mutation invalidates the affected keys after it resolves.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

// ─── Types (mirror backend/app/modules/crumb/schemas.py) ──────────────────────
// All money fields are Decimals serialized as exact STRINGS (D-11).

/** Lead lifecycle stage. */
export type LeadStatus = 'new' | 'qualified' | 'converted'

/** Opportunity pipeline stage. */
export type OpportunityStage = 'qualify' | 'proposal' | 'won' | 'lost'

/** Quote lifecycle status. */
export type QuoteStatus = 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired'

/** Interaction channel. */
export type InteractionType = 'call' | 'email' | 'note' | 'meeting'

/** Lead row (LeadRead). */
export interface Lead {
  id: string
  name: string
  company: string | null
  contact: string | null
  source: string | null
  status: string
  active: boolean
  partner_id: string | null
  opportunity_id: string | null
  actor_id: string
  created_at: string
}

/** Opportunity row (OpportunityRead). estimated_value is a STRING (D-11). */
export interface Opportunity {
  id: string
  name: string
  partner_id: string
  lead_id: string | null
  estimated_value: string | null
  expected_close_date: string | null
  stage: string
  actor_id: string
  created_at: string
}

/** Stage-grouped pipeline board (?pipeline=true). */
export type Pipeline = Record<string, Opportunity[]>

/** Quote header row (QuoteRead). */
export interface Quote {
  id: string
  quote_number: string
  partner_id: string
  opportunity_id: string | null
  status: string
  actor_id: string
  created_at: string
}

/** One priced quote line (QuoteLineRead). line_total is service-derived (D-11). */
export interface QuoteLine {
  id: string
  quote_id: string
  plum_part_id: string | null
  description: string | null
  quantity: string
  unit_price: string
  markup_pct: string | null
  sort_order: number
  line_total: string
}

/** Quote detail (QuoteDetailRead) — header plus its priced lines and total. */
export interface QuoteDetail extends Quote {
  lines: QuoteLine[]
  total_value: string
}

/** One customer-touch record (InteractionRead). */
export interface Interaction {
  id: string
  partner_id: string
  lead_id: string | null
  opportunity_id: string | null
  quote_id: string | null
  interaction_type: string
  occurred_at: string
  body: string
  actor_id: string
  created_at: string
}

// ─── Request payload types (mirror the Create/Update/Request schemas) ─────────

export interface LeadCreatePayload {
  name: string
  company?: string | null
  contact?: string | null
  source?: string | null
}

export interface LeadUpdatePayload {
  name?: string | null
  company?: string | null
  contact?: string | null
  source?: string | null
}

export interface LeadLinkCustomerPayload {
  partner_id?: string | null
  new_customer_name?: string | null
  is_customer?: boolean | null
  is_supplier?: boolean | null
}

export interface LeadConvertPayload {
  name: string
  estimated_value?: string | null
  expected_close_date?: string | null
}

export interface OpportunityCreatePayload {
  name: string
  partner_id: string
  estimated_value?: string | null
  expected_close_date?: string | null
  lead_id?: string | null
}

export interface OpportunityUpdatePayload {
  name?: string | null
  estimated_value?: string | null
  expected_close_date?: string | null
}

export interface QuoteLinePayload {
  plum_part_id?: string | null
  description?: string | null
  quantity: string
  unit_price?: string | null
  markup_pct?: string | null
}

export interface QuoteCreatePayload {
  partner_id: string
  opportunity_id?: string | null
  lines?: QuoteLinePayload[]
}

export interface SpawnQuotePayload {
  lines?: QuoteLinePayload[]
}

export interface InteractionCreatePayload {
  partner_id: string
  interaction_type: string
  body: string
  lead_id?: string | null
  opportunity_id?: string | null
  quote_id?: string | null
  occurred_at?: string | null
}

// ─── Query keys ───────────────────────────────────────────────────────────────

export const leadsKey = ['crumb', 'leads'] as const
export const leadKey = (id: string) => ['crumb', 'leads', id] as const
export const opportunitiesKey = ['crumb', 'opportunities'] as const
export const pipelineKey = ['crumb', 'pipeline'] as const
export const quotesKey = ['crumb', 'quotes'] as const
export const quoteKey = (id: string) => ['crumb', 'quotes', id] as const
export const timelineKey = (partnerId: string) => ['crumb', 'interactions', partnerId] as const

// ─── API helpers ──────────────────────────────────────────────────────────────

function fetchLeads(includeArchived: boolean): Promise<Lead[]> {
  return apiClient
    .get<Lead[]>('/api/v1/crumb/leads', { params: { include_archived: includeArchived } })
    .then((r) => r.data)
}

function fetchLead(id: string): Promise<Lead> {
  return apiClient.get<Lead>(`/api/v1/crumb/leads/${id}`).then((r) => r.data)
}

function fetchOpportunities(): Promise<Opportunity[]> {
  return apiClient.get<Opportunity[]>('/api/v1/crumb/opportunities').then((r) => r.data)
}

function fetchPipeline(): Promise<Pipeline> {
  return apiClient
    .get<Pipeline>('/api/v1/crumb/opportunities', { params: { pipeline: true } })
    .then((r) => r.data)
}

function fetchQuotes(): Promise<Quote[]> {
  return apiClient.get<Quote[]>('/api/v1/crumb/quotes').then((r) => r.data)
}

function fetchQuote(id: string): Promise<QuoteDetail> {
  return apiClient.get<QuoteDetail>(`/api/v1/crumb/quotes/${id}`).then((r) => r.data)
}

function fetchTimeline(partnerId: string): Promise<Interaction[]> {
  return apiClient
    .get<Interaction[]>('/api/v1/crumb/interactions', { params: { partner_id: partnerId } })
    .then((r) => r.data)
}

// ─── Queries ──────────────────────────────────────────────────────────────────

/** Lead list (archived excluded unless includeArchived). */
export function useLeads(includeArchived = false) {
  return useQuery<Lead[], Error>({
    queryKey: [...leadsKey, includeArchived] as const,
    queryFn: () => fetchLeads(includeArchived),
  })
}

/** One lead's detail. */
export function useLead(id: string) {
  return useQuery<Lead, Error>({
    queryKey: leadKey(id),
    queryFn: () => fetchLead(id),
    enabled: !!id,
  })
}

/** Opportunity list (flat, newest-first). */
export function useOpportunities() {
  return useQuery<Opportunity[], Error>({
    queryKey: opportunitiesKey,
    queryFn: fetchOpportunities,
  })
}

/** The stage-grouped pipeline board (?pipeline=true). */
export function usePipeline() {
  return useQuery<Pipeline, Error>({
    queryKey: pipelineKey,
    queryFn: fetchPipeline,
  })
}

/** Quote-header list. */
export function useQuotes() {
  return useQuery<Quote[], Error>({
    queryKey: quotesKey,
    queryFn: fetchQuotes,
  })
}

/** One quote's detail (header + priced lines + total). */
export function useQuote(id: string) {
  return useQuery<QuoteDetail, Error>({
    queryKey: quoteKey(id),
    queryFn: () => fetchQuote(id),
    enabled: !!id,
  })
}

/** A customer's interaction timeline (newest-first). */
export function useCustomerTimeline(partnerId: string) {
  return useQuery<Interaction[], Error>({
    queryKey: timelineKey(partnerId),
    queryFn: () => fetchTimeline(partnerId),
    enabled: !!partnerId,
  })
}

// ─── Mutations ────────────────────────────────────────────────────────────────

/** Create a lead. Invalidates the lead list. */
export function useCreateLead() {
  const qc = useQueryClient()
  return useMutation<Lead, Error, LeadCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post<Lead>('/api/v1/crumb/leads', payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: leadsKey })
    },
  })
}

/** PATCH a lead's descriptive fields. Invalidates the list and that lead. */
export function useUpdateLead() {
  const qc = useQueryClient()
  return useMutation<Lead, Error, { id: string; patch: LeadUpdatePayload }>({
    mutationFn: ({ id, patch }) =>
      apiClient.patch<Lead>(`/api/v1/crumb/leads/${id}`, patch).then((r) => r.data),
    onSuccess: (lead) => {
      qc.invalidateQueries({ queryKey: leadsKey })
      qc.invalidateQueries({ queryKey: leadKey(lead.id) })
    },
  })
}

/** Soft-archive a lead. Invalidates the list and that lead. */
export function useArchiveLead() {
  const qc = useQueryClient()
  return useMutation<Lead, Error, string>({
    mutationFn: (id) =>
      apiClient.post<Lead>(`/api/v1/crumb/leads/${id}/archive`).then((r) => r.data),
    onSuccess: (lead) => {
      qc.invalidateQueries({ queryKey: leadsKey })
      qc.invalidateQueries({ queryKey: leadKey(lead.id) })
    },
  })
}

/** Link a lead to a SYERP customer (existing or new). Invalidates the list and that lead. */
export function useLinkCustomer() {
  const qc = useQueryClient()
  return useMutation<Lead, Error, { id: string; payload: LeadLinkCustomerPayload }>({
    mutationFn: ({ id, payload }) =>
      apiClient
        .post<Lead>(`/api/v1/crumb/leads/${id}/link-customer`, payload)
        .then((r) => r.data),
    onSuccess: (lead) => {
      qc.invalidateQueries({ queryKey: leadsKey })
      qc.invalidateQueries({ queryKey: leadKey(lead.id) })
    },
  })
}

/** Convert a qualified lead into an opportunity. Invalidates leads and opportunities. */
export function useConvertLead() {
  const qc = useQueryClient()
  return useMutation<Opportunity, Error, { id: string; payload: LeadConvertPayload }>({
    mutationFn: ({ id, payload }) =>
      apiClient
        .post<Opportunity>(`/api/v1/crumb/leads/${id}/convert`, payload)
        .then((r) => r.data),
    onSuccess: (_opp, { id }) => {
      qc.invalidateQueries({ queryKey: leadsKey })
      qc.invalidateQueries({ queryKey: leadKey(id) })
      qc.invalidateQueries({ queryKey: opportunitiesKey })
      qc.invalidateQueries({ queryKey: pipelineKey })
    },
  })
}

/** Create an opportunity. Invalidates the list and the pipeline board. */
export function useCreateOpportunity() {
  const qc = useQueryClient()
  return useMutation<Opportunity, Error, OpportunityCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post<Opportunity>('/api/v1/crumb/opportunities', payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: opportunitiesKey })
      qc.invalidateQueries({ queryKey: pipelineKey })
    },
  })
}

/** PATCH an opportunity's fields (not stage). Invalidates the list and pipeline. */
export function useUpdateOpportunity() {
  const qc = useQueryClient()
  return useMutation<Opportunity, Error, { id: string; patch: OpportunityUpdatePayload }>({
    mutationFn: ({ id, patch }) =>
      apiClient
        .patch<Opportunity>(`/api/v1/crumb/opportunities/${id}`, patch)
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: opportunitiesKey })
      qc.invalidateQueries({ queryKey: pipelineKey })
    },
  })
}

/** Advance the opportunity stage FSM. Invalidates the list and pipeline. */
export function useAdvanceStage() {
  const qc = useQueryClient()
  return useMutation<Opportunity, Error, { id: string; target_stage: string }>({
    mutationFn: ({ id, target_stage }) =>
      apiClient
        .post<Opportunity>(`/api/v1/crumb/opportunities/${id}/stage`, { target_stage })
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: opportunitiesKey })
      qc.invalidateQueries({ queryKey: pipelineKey })
    },
  })
}

/** Spawn a draft quote from a won opportunity. Invalidates the quote list. */
export function useSpawnQuote() {
  const qc = useQueryClient()
  return useMutation<Quote, Error, { id: string; payload?: SpawnQuotePayload }>({
    mutationFn: ({ id, payload }) =>
      apiClient
        .post<Quote>(`/api/v1/crumb/opportunities/${id}/quote`, payload ?? {})
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: quotesKey })
    },
  })
}

/** Create a draft quote. Invalidates the quote list. */
export function useCreateQuote() {
  const qc = useQueryClient()
  return useMutation<Quote, Error, QuoteCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post<Quote>('/api/v1/crumb/quotes', payload).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: quotesKey })
    },
  })
}

/** Add a priced line to a draft quote. Invalidates that quote's detail. */
export function useAddQuoteLine() {
  const qc = useQueryClient()
  return useMutation<QuoteLine, Error, { quoteId: string; line: QuoteLinePayload }>({
    mutationFn: ({ quoteId, line }) =>
      apiClient
        .post<QuoteLine>(`/api/v1/crumb/quotes/${quoteId}/lines`, line)
        .then((r) => r.data),
    onSuccess: (_line, { quoteId }) => {
      qc.invalidateQueries({ queryKey: quoteKey(quoteId) })
    },
  })
}

/** Replace a draft quote line's priced fields. Invalidates that quote's detail. */
export function useUpdateQuoteLine() {
  const qc = useQueryClient()
  return useMutation<
    QuoteLine,
    Error,
    { quoteId: string; lineId: string; patch: QuoteLinePayload }
  >({
    mutationFn: ({ quoteId, lineId, patch }) =>
      apiClient
        .patch<QuoteLine>(`/api/v1/crumb/quotes/${quoteId}/lines/${lineId}`, patch)
        .then((r) => r.data),
    onSuccess: (_line, { quoteId }) => {
      qc.invalidateQueries({ queryKey: quoteKey(quoteId) })
    },
  })
}

/** Delete a line from a draft quote. Invalidates that quote's detail. */
export function useDeleteQuoteLine() {
  const qc = useQueryClient()
  return useMutation<void, Error, { quoteId: string; lineId: string }>({
    mutationFn: ({ quoteId, lineId }) =>
      apiClient
        .delete<void>(`/api/v1/crumb/quotes/${quoteId}/lines/${lineId}`)
        .then((r) => r.data),
    onSuccess: (_res, { quoteId }) => {
      qc.invalidateQueries({ queryKey: quoteKey(quoteId) })
    },
  })
}

/** Advance the quote status FSM. Invalidates the list and that quote's detail. */
export function useAdvanceQuoteStatus() {
  const qc = useQueryClient()
  return useMutation<Quote, Error, { id: string; target_status: string }>({
    mutationFn: ({ id, target_status }) =>
      apiClient
        .post<Quote>(`/api/v1/crumb/quotes/${id}/status`, { target_status })
        .then((r) => r.data),
    onSuccess: (quote) => {
      qc.invalidateQueries({ queryKey: quotesKey })
      qc.invalidateQueries({ queryKey: quoteKey(quote.id) })
    },
  })
}

/** Log one customer touch. Invalidates that customer's timeline. */
export function useCreateInteraction() {
  const qc = useQueryClient()
  return useMutation<Interaction, Error, InteractionCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post<Interaction>('/api/v1/crumb/interactions', payload).then((r) => r.data),
    onSuccess: (interaction) => {
      qc.invalidateQueries({ queryKey: timelineKey(interaction.partner_id) })
    },
  })
}

// ══ Sales orders (CRUMB-01, Phase 11b) ═══════════════════════════════════════
// Mirror the quote seam above: header list + detail (header + ordered lines),
// line CRUD (draft only), a status FSM, and quote→SO conversion. Money and
// quantity fields arrive as exact STRINGS (D-11) — render as-is, never float math.

/** Sales-order lifecycle status. */
export type SalesOrderStatus = 'draft' | 'confirmed' | 'fulfilling' | 'closed' | 'cancelled'

/** One ordered sales-order line (SalesOrderLineRead). line_total/shortage are service-derived. */
export interface SalesOrderLine {
  id: string
  sales_order_id: string
  item_id: string | null
  plum_part_id: string | null
  description: string | null
  qty_ordered: string
  unit_price: string
  qty_reserved: string
  sort_order: number
  line_total: string
  shortage: string
}

/** Sales-order header row (SalesOrderRead). */
export interface SalesOrder {
  id: string
  so_number: string
  partner_id: string
  source_quote_id: string | null
  source_opportunity_id: string | null
  status: string
  order_date: string
  required_date: string | null
  actor_id: string
  created_at: string
}

/** Sales-order detail (SalesOrderDetailRead) — header plus its ordered lines and total. */
export interface SalesOrderDetail extends SalesOrder {
  lines: SalesOrderLine[]
  total_value: string
}

/** One ordered line of a sales-order create / line-CRUD request (SalesOrderLineCreate). */
export interface SalesOrderLinePayload {
  item_id?: string | null
  plum_part_id?: string | null
  description?: string | null
  qty_ordered: string
  unit_price: string
}

export interface SalesOrderCreatePayload {
  partner_id: string
  order_date?: string | null
  required_date?: string | null
  lines?: SalesOrderLinePayload[]
}

/** Convert-quote-to-sales-order payload (QuoteToSalesOrderRequest) — thin by design. */
export interface QuoteConvertPayload {
  order_date?: string | null
  required_date?: string | null
}

export const salesOrdersKey = ['crumb', 'sales-orders'] as const
export const salesOrderKey = (id: string) => ['crumb', 'sales-orders', id] as const

function fetchSalesOrders(): Promise<SalesOrder[]> {
  return apiClient.get<SalesOrder[]>('/api/v1/crumb/sales-orders').then((r) => r.data)
}

function fetchSalesOrder(id: string): Promise<SalesOrderDetail> {
  return apiClient.get<SalesOrderDetail>(`/api/v1/crumb/sales-orders/${id}`).then((r) => r.data)
}

/** Sales-order header list (ordered by SO number). */
export function useSalesOrders() {
  return useQuery<SalesOrder[], Error>({
    queryKey: salesOrdersKey,
    queryFn: fetchSalesOrders,
  })
}

/** One sales order's detail (header + ordered lines + total). */
export function useSalesOrder(id: string) {
  return useQuery<SalesOrderDetail, Error>({
    queryKey: salesOrderKey(id),
    queryFn: () => fetchSalesOrder(id),
    enabled: !!id,
  })
}

/** Create a draft sales order (header + ordered lines). Invalidates the SO list. */
export function useCreateSalesOrder() {
  const qc = useQueryClient()
  return useMutation<SalesOrderDetail, Error, SalesOrderCreatePayload>({
    mutationFn: (payload) =>
      apiClient
        .post<SalesOrderDetail>('/api/v1/crumb/sales-orders', payload)
        .then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: salesOrdersKey })
    },
  })
}

/** Add an ordered line to a draft sales order. Invalidates that order's detail. */
export function useAddSoLine() {
  const qc = useQueryClient()
  return useMutation<SalesOrderLine, Error, { soId: string; line: SalesOrderLinePayload }>({
    mutationFn: ({ soId, line }) =>
      apiClient
        .post<SalesOrderLine>(`/api/v1/crumb/sales-orders/${soId}/lines`, line)
        .then((r) => r.data),
    onSuccess: (_line, { soId }) => {
      qc.invalidateQueries({ queryKey: salesOrderKey(soId) })
    },
  })
}

/** Replace a draft sales-order line. Invalidates that order's detail. */
export function useUpdateSoLine() {
  const qc = useQueryClient()
  return useMutation<
    SalesOrderLine,
    Error,
    { soId: string; lineId: string; patch: SalesOrderLinePayload }
  >({
    mutationFn: ({ soId, lineId, patch }) =>
      apiClient
        .patch<SalesOrderLine>(`/api/v1/crumb/sales-orders/${soId}/lines/${lineId}`, patch)
        .then((r) => r.data),
    onSuccess: (_line, { soId }) => {
      qc.invalidateQueries({ queryKey: salesOrderKey(soId) })
    },
  })
}

/** Delete a line from a draft sales order. Invalidates that order's detail. */
export function useDeleteSoLine() {
  const qc = useQueryClient()
  return useMutation<void, Error, { soId: string; lineId: string }>({
    mutationFn: ({ soId, lineId }) =>
      apiClient
        .delete<void>(`/api/v1/crumb/sales-orders/${soId}/lines/${lineId}`)
        .then((r) => r.data),
    onSuccess: (_res, { soId }) => {
      qc.invalidateQueries({ queryKey: salesOrderKey(soId) })
    },
  })
}

/** Advance the sales-order status FSM. Invalidates the list and that order's detail. */
export function useAdvanceSalesOrderStatus() {
  const qc = useQueryClient()
  return useMutation<SalesOrderDetail, Error, { id: string; target_status: string }>({
    mutationFn: ({ id, target_status }) =>
      apiClient
        .post<SalesOrderDetail>(`/api/v1/crumb/sales-orders/${id}/status`, { target_status })
        .then((r) => r.data),
    onSuccess: (so) => {
      qc.invalidateQueries({ queryKey: salesOrdersKey })
      qc.invalidateQueries({ queryKey: salesOrderKey(so.id) })
    },
  })
}

/**
 * Convert an accepted quote into a draft sales order. Invalidates the SO list and
 * the source quote (whose status moves to converted).
 */
export function useConvertQuoteToSalesOrder() {
  const qc = useQueryClient()
  return useMutation<
    SalesOrderDetail,
    Error,
    { quoteId: string; payload?: QuoteConvertPayload }
  >({
    mutationFn: ({ quoteId, payload }) =>
      apiClient
        .post<SalesOrderDetail>(`/api/v1/crumb/quotes/${quoteId}/convert`, payload ?? {})
        .then((r) => r.data),
    onSuccess: (_so, { quoteId }) => {
      qc.invalidateQueries({ queryKey: salesOrdersKey })
      qc.invalidateQueries({ queryKey: quotesKey })
      qc.invalidateQueries({ queryKey: quoteKey(quoteId) })
    },
  })
}
