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

// ─── Query keys ───────────────────────────────────────────────────────────────

export const binsKey = (locationId: number) => ['gelato', 'bins', locationId] as const
export const unbinnedKey = (locationId: number) => ['gelato', 'unbinned', locationId] as const
export const suggestionKey = (itemId: string, locationId: number) =>
  ['gelato', 'putaway', 'suggestion', itemId, locationId] as const
/** SYERP item on-hand key — invalidated after a putaway moves the item's ledger legs. */
const itemOnHandKey = (itemId: string) =>
  ['syerp', 'inventory', 'items', itemId, 'onhand'] as const

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
