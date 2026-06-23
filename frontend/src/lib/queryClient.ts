import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Don't refetch on window focus in production — reduces noise for self-hosted deployments
      refetchOnWindowFocus: false,
      // Retry once on failure before showing error state
      retry: 1,
      // Consider data stale after 30 seconds
      staleTime: 30_000,
    },
  },
})
