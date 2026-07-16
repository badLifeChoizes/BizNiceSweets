// ABOUTME: Shared FastAPI error-message extractor for CRUMB screens — turns a failed
// ABOUTME: request into the server's real reason (string `detail` or a 422 validation
// ABOUTME: array of { loc, msg }) so mutations can surface it via a sonner toast.

import axios from 'axios'

/**
 * Pull a human-readable message out of a failed request. FastAPI returns either a
 * string `detail` (business-rule 4xx) or a 422 validation array of { loc, msg };
 * anything else falls back to the supplied default.
 */
export function getApiErrorMessage(err: unknown, fallback: string): string {
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
