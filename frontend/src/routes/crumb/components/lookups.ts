// ABOUTME: Shared cross-module lookup queries for CRUMB screens — SYERP customer
// ABOUTME: partners (for picking a customer) and PLUM parts (for the quote line editor).
// ABOUTME: Both are cached briefly so the dialogs that reuse them don't refetch on open.

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { PartnerRead } from '../../syerp/components/PartnerSheet'
import type { PartRead } from '../../plum/components/PartSheet'

export type { PartnerRead, PartRead }

function fetchCustomers(): Promise<PartnerRead[]> {
  return apiClient
    .get<PartnerRead[]>('/api/v1/syerp/partners?role=customer')
    .then((r) => r.data)
}

/** SYERP customer partners — the pool a lead/opportunity/quote can point at. */
export function useCustomers(enabled = true) {
  return useQuery<PartnerRead[], Error>({
    queryKey: ['syerp', 'partners', 'customer'],
    queryFn: fetchCustomers,
    enabled,
    staleTime: 60 * 1000,
  })
}

function fetchParts(): Promise<PartRead[]> {
  return apiClient.get<PartRead[]>('/api/v1/plum/parts').then((r) => r.data)
}

/** PLUM parts — the pool the quote line editor prices from. */
export function usePlumParts(enabled = true) {
  return useQuery<PartRead[], Error>({
    queryKey: ['plum', 'parts'],
    queryFn: fetchParts,
    enabled,
    staleTime: 60 * 1000,
  })
}
