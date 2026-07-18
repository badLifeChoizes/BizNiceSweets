// ABOUTME: GELATO (Warehouse Management) TanStack Query hooks + shared request/response
// ABOUTME: types. Wraps the /api/v1/gelato/* API (bins CRUD, unbinned stock, putaway
// ABOUTME: suggestion, execute putaway) through the single axios client. Quantity fields
// ABOUTME: arrive as exact STRINGS (D-11) — render as-is, never float math.

/**
 * GELATO bins & directed-putaway hooks — the query seam shared by the Bins and
 * Putaway screens (GELATO-01).
 *
 * Query keys (kept in one place so mutations can invalidate consistently):
 *   ['gelato', 'bins', locationId]                       — the bins in one location
 *   ['gelato', 'unbinned', locationId]                   — unbinned stock awaiting putaway
 *   ['gelato', 'putaway', 'suggestion', itemId, locationId] — suggested target bin
 *
 * Reads are GETs; putaway invalidates the affected bins + unbinned keys and the
 * moved item's SYERP on-hand (the putaway posts two mirrored ledger legs).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'

// ─── Types (mirror backend/app/modules/gelato/schemas.py) ─────────────────────
// All quantity/cost fields are Decimals serialized as exact STRINGS (D-11).

/** Bin row (BinRead) — one storage bin subdividing a SYERP stock location. */
export interface Bin {
  id: number
  location_id: number
  code: string
  description: string | null
  active: boolean
  created_at: string
}

/** One unbinned-stock row awaiting putaway (UnbinnedStockRead). unbinned_qty is a STRING (D-11). */
export interface UnbinnedStock {
  item_id: string
  location_id: number
  unbinned_qty: string
  suggested_bin_id: number | null
}

/** One immutable inventory-ledger row (SYERP TransactionRead). quantity/unit_cost are STRINGS (D-11). */
export interface Transaction {
  id: string
  item_id: string
  location_id: number
  location_name: string
  txn_type: string
  quantity: string
  unit_cost: string | null
  reason: string | null
  created_at: string
}

/** Result of a putaway posting (PutawayResult) — the two mirrored legs plus resulting totals. */
export interface PutawayResult {
  out_leg: Transaction
  in_leg: Transaction
  bin_on_hand: string
  location_total: string
}

/** Suggested target bin ({"suggested_bin_id": <int|null>}). */
export interface PutawaySuggestion {
  suggested_bin_id: number | null
}

// ─── Shipment pick/pack/ship types (mirror ShipmentRead / PickListRead) ───────

/** One shipment line (ShipmentLineRead). qty is a STRING (D-11). */
export interface ShipmentLine {
  id: number
  sales_order_line_id: string
  item_id: string
  from_bin_id: number
  qty: string
  inventory_txn_id: string | null
}

/** A shipment (ShipmentRead) — the outbound pick→pack→ship FSM record. */
export interface Shipment {
  id: number
  sales_order_id: string
  location_id: number
  staging_bin_id: number
  status: string
  journal_entry_id: string | null
  lines: ShipmentLine[]
  created_at: string
}

/** One candidate source bin for a pick-list line (PickListBinRead). on_hand is a STRING (D-11). */
export interface PickListBin {
  bin_id: number
  code: string
  on_hand: string
}

/** One pick-list line (PickListLineRead) — all quantities are STRINGS (D-11). */
export interface PickListLine {
  sales_order_line_id: string
  item_id: string
  description: string
  qty_ordered: string
  qty_reserved: string
  qty_picked: string
  qty_shipped: string
  suggested_from_bin_id: number | null
  available_bins: PickListBin[]
}

/** The pick list for a sales order (PickListRead). */
export interface PickList {
  sales_order_id: string
  lines: PickListLine[]
}

// ─── Request payload types (mirror the Create/Update/Request schemas) ─────────

export interface BinCreatePayload {
  location_id: number
  code: string
  description?: string | null
}

export interface BinUpdatePayload {
  description?: string | null
  active?: boolean | null
}

export interface PutawayPayload {
  item_id: string
  location_id: number
  to_bin_id: number
  qty: string
  from_bin_id?: number | null
}

/** One line of a pick payload (PickLineRequest) — pick qty of a SO line from a bin. */
export interface PickLinePayload {
  sales_order_line_id: string
  from_bin_id: number
  qty: string
}

/** Pick payload (PickRequest) — pick a whole SO into a staging bin. */
export interface PickPayload {
  sales_order_id: string
  staging_bin_id: number
  lines: PickLinePayload[]
}

/** One per-line staged-qty override for packing (PackLineOverride). */
export interface PackLineOverride {
  shipment_line_id: number
  qty: string
}

/** Pack payload (PackRequest) — confirm the staged shipment; overrides default to []. */
export interface PackPayload {
  overrides?: PackLineOverride[]
}

// ─── Query keys ───────────────────────────────────────────────────────────────

export const binsKey = (locationId: number) => ['gelato', 'bins', locationId] as const
export const unbinnedKey = (locationId: number) => ['gelato', 'unbinned', locationId] as const
export const suggestionKey = (itemId: string, locationId: number) =>
  ['gelato', 'putaway', 'suggestion', itemId, locationId] as const
/** SYERP item on-hand key — invalidated after a putaway moves the item's ledger legs. */
const itemOnHandKey = (itemId: string) =>
  ['syerp', 'inventory', 'items', itemId, 'onhand'] as const
export const pickListKey = (soId: string) => ['gelato', 'pick-list', soId] as const
export const shipmentKey = (id: number) => ['gelato', 'shipments', id] as const
/** CRUMB sales-order detail key — invalidated when reserved/picked/shipped figures move. */
const soDetailKey = (soId: string) => ['crumb', 'sales-orders', soId] as const

// ─── API helpers ──────────────────────────────────────────────────────────────

function fetchBins(locationId: number, includeArchived: boolean): Promise<Bin[]> {
  return apiClient
    .get<Bin[]>(`/api/v1/gelato/locations/${locationId}/bins`, {
      params: { include_archived: includeArchived },
    })
    .then((r) => r.data)
}

function fetchUnbinnedStock(locationId: number): Promise<UnbinnedStock[]> {
  return apiClient
    .get<UnbinnedStock[]>(`/api/v1/gelato/locations/${locationId}/unbinned`)
    .then((r) => r.data)
}

function fetchSuggestion(itemId: string, locationId: number): Promise<PutawaySuggestion> {
  return apiClient
    .get<PutawaySuggestion>('/api/v1/gelato/putaway/suggestion', {
      params: { item_id: itemId, location_id: locationId },
    })
    .then((r) => r.data)
}

function fetchPickList(soId: string): Promise<PickList> {
  return apiClient
    .get<PickList>(`/api/v1/gelato/sales-orders/${soId}/pick-list`)
    .then((r) => r.data)
}

function fetchShipment(id: number): Promise<Shipment> {
  return apiClient.get<Shipment>(`/api/v1/gelato/shipments/${id}`).then((r) => r.data)
}

// ─── Queries ──────────────────────────────────────────────────────────────────

/** Bins in one stock location (archived excluded unless includeArchived). */
export function useBins(locationId: number, includeArchived = false) {
  return useQuery<Bin[], Error>({
    queryKey: [...binsKey(locationId), includeArchived] as const,
    queryFn: () => fetchBins(locationId, includeArchived),
    enabled: !!locationId,
  })
}

/** Unbinned stock at a location, awaiting putaway (each row carries a suggested bin). */
export function useUnbinnedStock(locationId: number) {
  return useQuery<UnbinnedStock[], Error>({
    queryKey: unbinnedKey(locationId),
    queryFn: () => fetchUnbinnedStock(locationId),
    enabled: !!locationId,
  })
}

/** The suggested target bin for an item at a location (D-P12a-10 heuristic). */
export function usePutawaySuggestion(itemId: string, locationId: number) {
  return useQuery<PutawaySuggestion, Error>({
    queryKey: suggestionKey(itemId, locationId),
    queryFn: () => fetchSuggestion(itemId, locationId),
    enabled: !!itemId && !!locationId,
  })
}

/** The pick list for a sales order — per-line pick suggestions + candidate bins (SC2). */
export function usePickList(soId: string) {
  return useQuery<PickList, Error>({
    queryKey: pickListKey(soId),
    queryFn: () => fetchPickList(soId),
    enabled: !!soId,
  })
}

/** One shipment with its lines (pick→pack→ship FSM record). */
export function useShipment(id: number) {
  return useQuery<Shipment, Error>({
    queryKey: shipmentKey(id),
    queryFn: () => fetchShipment(id),
    enabled: !!id,
  })
}

// ─── Mutations ────────────────────────────────────────────────────────────────

/** Create a bin. Invalidates that location's bins. */
export function useCreateBin() {
  const qc = useQueryClient()
  return useMutation<Bin, Error, BinCreatePayload>({
    mutationFn: (payload) =>
      apiClient.post<Bin>('/api/v1/gelato/bins', payload).then((r) => r.data),
    onSuccess: (bin) => {
      qc.invalidateQueries({ queryKey: binsKey(bin.location_id) })
    },
  })
}

/** PATCH a bin's description and/or active flag. Invalidates that location's bins. */
export function useUpdateBin() {
  const qc = useQueryClient()
  return useMutation<Bin, Error, { id: number; patch: BinUpdatePayload }>({
    mutationFn: ({ id, patch }) =>
      apiClient.patch<Bin>(`/api/v1/gelato/bins/${id}`, patch).then((r) => r.data),
    onSuccess: (bin) => {
      qc.invalidateQueries({ queryKey: binsKey(bin.location_id) })
    },
  })
}

/** Soft-archive a bin. Invalidates that location's bins. */
export function useArchiveBin() {
  const qc = useQueryClient()
  return useMutation<Bin, Error, number>({
    mutationFn: (id) =>
      apiClient.post<Bin>(`/api/v1/gelato/bins/${id}/archive`).then((r) => r.data),
    onSuccess: (bin) => {
      qc.invalidateQueries({ queryKey: binsKey(bin.location_id) })
    },
  })
}

/**
 * Execute a putaway (move qty of an item into a bin). Invalidates the location's
 * bins + unbinned stock and the moved item's SYERP on-hand (the two ledger legs).
 */
export function useExecutePutaway() {
  const qc = useQueryClient()
  return useMutation<PutawayResult, Error, PutawayPayload>({
    mutationFn: (payload) =>
      apiClient.post<PutawayResult>('/api/v1/gelato/putaway', payload).then((r) => r.data),
    onSuccess: (_result, { location_id, item_id }) => {
      qc.invalidateQueries({ queryKey: binsKey(location_id) })
      qc.invalidateQueries({ queryKey: unbinnedKey(location_id) })
      qc.invalidateQueries({ queryKey: itemOnHandKey(item_id) })
    },
  })
}

/**
 * Pick a sales order into staging (POST /gelato/shipments/pick). Invalidates the
 * location's bins + unbinned stock, each picked item's SYERP on-hand, the SO's
 * detail (reservation/shortage figures) and its pick list.
 */
export function useExecutePick() {
  const qc = useQueryClient()
  return useMutation<Shipment, Error, PickPayload>({
    mutationFn: (payload) =>
      apiClient.post<Shipment>('/api/v1/gelato/shipments/pick', payload).then((r) => r.data),
    onSuccess: (shipment, { sales_order_id }) => {
      qc.invalidateQueries({ queryKey: binsKey(shipment.location_id) })
      qc.invalidateQueries({ queryKey: unbinnedKey(shipment.location_id) })
      for (const line of shipment.lines) {
        qc.invalidateQueries({ queryKey: itemOnHandKey(line.item_id) })
      }
      qc.invalidateQueries({ queryKey: soDetailKey(sales_order_id) })
      qc.invalidateQueries({ queryKey: pickListKey(sales_order_id) })
    },
  })
}

/**
 * Pack a picked shipment (POST /gelato/shipments/{id}/pack). A pure state + staged-qty
 * record (no ledger movement), so it only invalidates the shipment and its pick list.
 */
export function useExecutePack() {
  const qc = useQueryClient()
  return useMutation<Shipment, Error, { shipmentId: number; payload: PackPayload }>({
    mutationFn: ({ shipmentId, payload }) =>
      apiClient
        .post<Shipment>(`/api/v1/gelato/shipments/${shipmentId}/pack`, payload)
        .then((r) => r.data),
    onSuccess: (shipment) => {
      qc.invalidateQueries({ queryKey: shipmentKey(shipment.id) })
      qc.invalidateQueries({ queryKey: pickListKey(shipment.sales_order_id) })
    },
  })
}

/**
 * Ship a packed shipment (POST /gelato/shipments/{id}/ship, empty body). Invalidates
 * the same set as pick (bins, unbinned, each item's on-hand, SO detail, pick list)
 * PLUS the shipment itself — shipping issues stock and posts the COGS JE.
 */
export function useExecuteShip() {
  const qc = useQueryClient()
  return useMutation<Shipment, Error, number>({
    mutationFn: (shipmentId) =>
      apiClient
        .post<Shipment>(`/api/v1/gelato/shipments/${shipmentId}/ship`, {})
        .then((r) => r.data),
    onSuccess: (shipment) => {
      qc.invalidateQueries({ queryKey: binsKey(shipment.location_id) })
      qc.invalidateQueries({ queryKey: unbinnedKey(shipment.location_id) })
      for (const line of shipment.lines) {
        qc.invalidateQueries({ queryKey: itemOnHandKey(line.item_id) })
      }
      qc.invalidateQueries({ queryKey: soDetailKey(shipment.sales_order_id) })
      qc.invalidateQueries({ queryKey: pickListKey(shipment.sales_order_id) })
      qc.invalidateQueries({ queryKey: shipmentKey(shipment.id) })
    },
  })
}
