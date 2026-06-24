/**
 * In-memory access token storage.
 * The token lives only in this module-level variable — never in localStorage or
 * sessionStorage — so an XSS attack cannot persist-exfiltrate it across page loads.
 * (RESEARCH.md anti-pattern; threat T-02-18)
 */

let _accessToken: string | null = null

export function getAccessToken(): string | null {
  return _accessToken
}

export function setAccessToken(token: string): void {
  _accessToken = token
}

export function clearAccessToken(): void {
  _accessToken = null
}
