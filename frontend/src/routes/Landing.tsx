import { useQuery } from '@tanstack/react-query'
import { cn } from '@/lib/utils'

interface HealthResponse {
  status: string
  db?: string
}

async function fetchHealth(path: string): Promise<HealthResponse> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<HealthResponse>
}

export function Landing() {
  const liveness = useQuery<HealthResponse, Error>({
    queryKey: ['health', 'live'],
    queryFn: () => fetchHealth('/health/live'),
  })

  const readiness = useQuery<HealthResponse, Error>({
    queryKey: ['health', 'ready'],
    queryFn: () => fetchHealth('/health/ready'),
  })

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-8">
      <div className="max-w-lg w-full space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-foreground">BizNiceSweets</h1>
          <p className="text-muted-foreground text-lg">
            Modular business suite for small manufacturers
          </p>
        </div>

        {/* Health Status Cards */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            System Status
          </h2>

          {/* Liveness */}
          <HealthCard
            label="API Process"
            description="Liveness — is the backend process alive?"
            isPending={liveness.isPending}
            isError={liveness.isError}
            data={liveness.data}
            error={liveness.error}
          />

          {/* Readiness */}
          <HealthCard
            label="Database Connection"
            description="Readiness — can the backend reach PostgreSQL?"
            isPending={readiness.isPending}
            isError={readiness.isError}
            data={readiness.data}
            error={readiness.error}
          />
        </div>

        {/* Footer hint */}
        <p className="text-center text-xs text-muted-foreground">
          Phase 1 skeleton &mdash; auth, modules, and app shell arrive in later phases
        </p>
      </div>
    </div>
  )
}

interface HealthCardProps {
  label: string
  description: string
  isPending: boolean
  isError: boolean
  data?: HealthResponse
  error: Error | null
}

function HealthCard({ label, description, isPending, isError, data, error }: HealthCardProps) {
  const statusColor = isPending
    ? 'bg-yellow-400'
    : isError
      ? 'bg-red-500'
      : data?.status === 'ok'
        ? 'bg-green-500'
        : 'bg-gray-400'

  const statusText = isPending
    ? 'Checking…'
    : isError
      ? 'Unreachable'
      : data?.status === 'ok'
        ? 'Connected'
        : 'Unknown'

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card p-4 flex items-start gap-4',
        isError && 'border-red-300'
      )}
    >
      <div className={cn('mt-1 h-3 w-3 rounded-full flex-shrink-0', statusColor)} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="font-medium text-card-foreground">{label}</span>
          <span
            className={cn(
              'text-sm font-medium',
              isPending
                ? 'text-yellow-600'
                : isError
                  ? 'text-red-600'
                  : 'text-green-600'
            )}
          >
            {statusText}
          </span>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        {isError && error && (
          <p className="text-xs text-red-600 mt-1 font-mono">{error.message}</p>
        )}
        {!isPending && !isError && data?.db && (
          <p className="text-xs text-green-700 mt-1">db: {data.db}</p>
        )}
      </div>
    </div>
  )
}
