/**
 * Modules — admin Module enable/disable screen (D-09, CORE-07).
 *
 * Table columns: Module name (display_name), Status badge, Enable toggle (Switch).
 * SYERP row: Switch disabled + tooltip (D-08 UI reflection of backend always-on guard).
 *
 * Toggle mutation: PATCH /api/v1/core/modules/{key} { enabled }
 *   onSuccess: invalidateQueries(['core', 'modules']) — MUST match useModules key (Pitfall 6)
 *   onError 422: snap Switch back; toast "SYERP cannot be disabled."
 *   onError 403: toast "You don't have permission to change module settings."
 *   other errors: toast "Failed to update module. Please try again."
 *
 * Switch disabled while mutation is pending to prevent double-toggle.
 * No confirmation modal — toggle is reversible (UI-SPEC destructive-actions table).
 *
 * Typography: font-semibold (600) for module name cell + headings; font-normal (400) elsewhere.
 */

import { useState } from 'react'
import { toast } from 'sonner'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useModules, type ModuleRecord } from '@/hooks/useModules'
import { apiClient } from '@/api/client'
import axios from 'axios'

// ─── Toggle mutation ──────────────────────────────────────────────────────────

interface TogglePayload {
  key: string
  enabled: boolean
}

function toggleModule({ key, enabled }: TogglePayload): Promise<ModuleRecord> {
  return apiClient
    .patch<ModuleRecord>(`/api/v1/core/modules/${key}`, { enabled })
    .then((r) => r.data)
}

// ─── Module row ───────────────────────────────────────────────────────────────

interface ModuleRowProps {
  mod: ModuleRecord
  isPending: boolean
  onToggle: (key: string, enabled: boolean) => void
}

function ModuleRow({ mod, isPending, onToggle }: ModuleRowProps) {
  return (
    <TableRow key={mod.key}>
      {/* Module name */}
      <TableCell className="font-semibold text-sm text-foreground">
        {mod.display_name}
      </TableCell>

      {/* Status badge */}
      <TableCell>
        {mod.always_on ? (
          <Badge variant="secondary">Always On</Badge>
        ) : (
          <Badge
            variant="outline"
            className={mod.enabled ? 'text-foreground' : 'text-muted-foreground'}
          >
            {mod.enabled ? 'Enabled' : 'Disabled'}
          </Badge>
        )}
      </TableCell>

      {/* Enable toggle */}
      <TableCell>
        {mod.always_on ? (
          // Disabled with tooltip — D-08 (T-03-11)
          <span
            title="SYERP is the core hub and cannot be disabled."
            className="inline-flex cursor-not-allowed"
          >
            <Switch
              checked={true}
              disabled={true}
              aria-label={`${mod.display_name} module toggle — always on`}
            />
          </span>
        ) : (
          <Switch
            checked={mod.enabled}
            disabled={isPending}
            onCheckedChange={(checked) => onToggle(mod.key, checked)}
            aria-label={`Toggle ${mod.display_name} module ${mod.enabled ? 'off' : 'on'}`}
          />
        )}
      </TableCell>
    </TableRow>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Modules() {
  const queryClient = useQueryClient()
  const { data: modules = [], isLoading } = useModules()

  // Track which module key is currently being toggled (for per-row pending state)
  const [pendingKey, setPendingKey] = useState<string | null>(null)

  // Optimistic UI: track local overrides for switch state during pending
  const [localOverrides, setLocalOverrides] = useState<Record<string, boolean>>({})

  const toggleMutation = useMutation<ModuleRecord, Error, TogglePayload>({
    mutationFn: toggleModule,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['core', 'modules'] })
      setPendingKey(null)
      setLocalOverrides({})
    },
    onError: (err, variables) => {
      // Snap Switch back to previous state on error
      setLocalOverrides((prev) => ({ ...prev, [variables.key]: !variables.enabled }))
      setPendingKey(null)

      if (axios.isAxiosError(err)) {
        const status = err.response?.status
        if (status === 422) {
          toast.error('SYERP cannot be disabled.')
          return
        }
        if (status === 403) {
          toast.error("You don't have permission to change module settings.")
          return
        }
      }
      toast.error('Failed to update module. Please try again.')
    },
  })

  function handleToggle(key: string, enabled: boolean) {
    // Optimistically update the switch state
    setLocalOverrides((prev) => ({ ...prev, [key]: enabled }))
    setPendingKey(key)
    toggleMutation.mutate({ key, enabled })
  }

  // Merge server data with local optimistic overrides
  const displayModules = modules.map((mod) =>
    Object.prototype.hasOwnProperty.call(localOverrides, mod.key)
      ? { ...mod, enabled: localOverrides[mod.key] }
      : mod,
  )

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Modules</h1>
        <p className="text-sm font-normal text-muted-foreground">
          Enable or disable modules for your deployment. Always-on modules cannot be disabled.
        </p>
      </div>

      {/* Modules table */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Module</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Enable</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayModules.map((mod) => (
              <ModuleRow
                key={mod.key}
                mod={mod}
                isPending={pendingKey === mod.key}
                onToggle={handleToggle}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
