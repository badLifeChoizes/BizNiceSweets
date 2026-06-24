/**
 * Login page — UI-SPEC Screen 1.
 *
 * Layout: centered Card (max-w-[400px]) on min-h-screen bg-background.
 * Copy and states follow the UI design contract exactly (02-UI-SPEC.md copywriting table).
 *
 * Security constraints honored:
 *   D-01: No "Create account" link — accounts are admin-provisioned.
 *   D-13: No "Forgot password" link — recovery is admin-reset-first.
 *   D-06: On success, access token stored in memory via setAccessToken (not localStorage).
 *
 * The login form submits as OAuth2 form data (username=email, password) to match
 * the FastAPI OAuth2PasswordRequestForm on the backend.
 */

import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { apiClient } from '@/api/client'
import { setAccessToken } from '@/auth/token'
import { cn } from '@/lib/utils'

interface TokenResponse {
  access_token: string
  token_type: string
}

interface LocationState {
  from?: Location
}

function loginRequest(email: string, password: string): Promise<TokenResponse> {
  // OAuth2PasswordRequestForm expects form data: username + password fields
  const formData = new URLSearchParams()
  formData.append('username', email)
  formData.append('password', password)
  return apiClient
    .post<TokenResponse>('/api/v1/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    .then((r) => r.data)
}

export function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const locationState = location.state as LocationState | null
  const from = locationState?.from?.pathname ?? '/'

  const mutation = useMutation<TokenResponse, Error, { email: string; password: string }>({
    mutationFn: ({ email, password }) => loginRequest(email, password),
    onSuccess: (data) => {
      setAccessToken(data.access_token)
      void queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
      void navigate(from, { replace: true })
    },
  })

  const isLoading = mutation.isPending
  const error = mutation.error

  function getErrorMessage(err: Error | null): string {
    if (!err) return ''
    if (axios.isAxiosError(err)) {
      if (err.response?.status === 401) {
        return 'Incorrect email or password. Check your credentials and try again.'
      }
      if (!err.response) {
        return 'Unable to reach the server. Check that the backend is running.'
      }
    }
    return 'Unable to reach the server. Check that the backend is running.'
  }

  const errorMessage = getErrorMessage(error)
  const hasError = Boolean(errorMessage)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    mutation.mutate({ email, password })
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-8">
      <div className="w-full max-w-[400px] space-y-6">
        {/* Display heading + subheading */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-semibold text-foreground">BizNiceSweets</h1>
          <p className="text-base text-muted-foreground">Sign in to your account</p>
        </div>

        {/* Login card */}
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              {/* Email field */}
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={cn(hasError && 'border-destructive')}
                  disabled={isLoading}
                  aria-describedby={hasError ? 'login-error' : undefined}
                />
              </div>

              {/* Password field with show/hide toggle */}
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={cn('pr-10', hasError && 'border-destructive')}
                    disabled={isLoading}
                    aria-describedby={hasError ? 'login-error' : undefined}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                    tabIndex={0}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              {/* Submit button */}
              <Button type="submit" className="w-full" variant="default" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="animate-spin" aria-hidden="true" />
                    Signing in…
                  </>
                ) : (
                  'Sign In'
                )}
              </Button>

              {/* Inline error message */}
              {hasError && (
                <p
                  id="login-error"
                  role="alert"
                  className="text-sm text-red-600"
                >
                  {errorMessage}
                </p>
              )}
            </form>
          </CardContent>
        </Card>
        {/* D-01: No "Create account" link */}
        {/* D-13: No "Forgot password" link */}
      </div>
    </div>
  )
}
