// ABOUTME: Create/edit Dialog for a FLAN roster member (FLAN-01.4) — name, role, email,
// ABOUTME: colour, hourly rate and an OPTIONAL platform-user link whose "No platform user"
// ABOUTME: option posts `user_id: null`. The rate carries the helper text saying nothing
// ABOUTME: derives a cost from it in v5.0 (D-V5-2 / D-M5-2); it is a STRING on the wire.

/**
 * MemberDialog — the shared create/edit form for a project's roster.
 *
 * Props:
 *   open: boolean            — controls dialog visibility
 *   projectId: string        — the URL's project (D-V5P1-3); scopes the POST
 *   member: TeamMember|null  — the row being edited; null is the create case
 *   onClose: () => void      — called on save success and on Cancel
 *
 * Three rules are load-bearing here:
 *
 *   - **The platform-user link is optional, and "no user" is a real answer.**
 *     A member with no `user_id` is a full collaborator (roster.py) — listed,
 *     assignable, indistinguishable from a linked one except for the link. The
 *     Select therefore opens on "No platform user" and posts `user_id: null`,
 *     never `''` (which is not a user id) and never an omitted key (which would
 *     leave a PATCH's existing link in place instead of clearing it).
 *   - **`hourly_rate` crosses the wire as a STRING** (a Decimal — D-11). The
 *     input is a text field, its value is trimmed and sent verbatim, and a blank
 *     one is sent as null: `parseFloat`ing it here would round the shop's own
 *     figure on the client's terms before the server ever saw it.
 *   - **Nothing reads `hourly_rate` in v5.0** (D-V5-2 / D-M5-2). No rollup,
 *     report or endpoint in this release derives a cost from it, so the field
 *     says so in its own helper text rather than letting a user infer a costing
 *     feature that does not exist.
 *
 * The user list itself comes from ./platformUsers (an AUTH endpoint, so it is
 * not in flan/hooks.ts); the Team screen shares the same cached query to label
 * its "Platform user" column, and both degrade to the unlinked case when the
 * caller may not list users.
 *
 * Every key in the POST/PATCH body exists in the backend's TeamMemberCreate /
 * TeamMemberUpdate: name, role, email, color, hourly_rate, user_id. `active` is
 * in neither — removal is its own endpoint and a soft-remove (D-V5P1-6).
 *
 * Mirrors routes/flan/Phases.tsx::PhaseFormDialog (local field state, one
 * mutation from ../hooks, `getApiErrorMessage` on the failure path so a 4xx is
 * reported in the server's own words).
 */

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { getApiErrorMessage } from '@/routes/crumb/components/apiError'
import { useCreateMember, useUpdateMember } from '../hooks'
import type { TeamMember } from '../hooks'
import { platformUserLabel, usePlatformUsers } from './platformUsers'

// ─── Constants ───────────────────────────────────────────────────────────────

/**
 * Sentinel for "this member is linked to no platform user". Radix forbids an
 * empty SelectItem value, so the unlinked case needs a value of its own; it is
 * translated back to a literal `null` in the payload, never sent as-is.
 */
const NO_USER = '__none__'

/** The one sentence the rate field owes the user (D-V5-2 / D-M5-2). */
const RATE_HELPER = 'stored for a later milestone; no cost is derived from it in v5.0'

// ─── Props ───────────────────────────────────────────────────────────────────

interface MemberDialogProps {
  open: boolean
  projectId: string
  member: TeamMember | null
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function MemberDialog({ open, projectId, member, onClose }: MemberDialogProps) {
  const { data: users = [] } = usePlatformUsers()

  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [email, setEmail] = useState('')
  const [color, setColor] = useState('')
  const [hourlyRate, setHourlyRate] = useState('')
  const [userId, setUserId] = useState<string>(NO_USER)

  // Seed on open: the edited member's own values, or a blank create form. The
  // rate seeds VERBATIM — the string the API returned, not a re-formatted one.
  useEffect(() => {
    if (!open) return
    setName(member?.name ?? '')
    setRole(member?.role ?? '')
    setEmail(member?.email ?? '')
    setColor(member?.color ?? '')
    setHourlyRate(member?.hourly_rate ?? '')
    setUserId(member?.user_id ?? NO_USER)
  }, [open, member])

  const createMutation = useCreateMember()
  const updateMutation = useUpdateMember()
  const isEditing = member !== null
  const isSaving = createMutation.isPending || updateMutation.isPending
  const canSubmit = name.trim() !== ''

  function handleSubmit() {
    if (!canSubmit) return
    // Every key below exists in TeamMemberCreate / TeamMemberUpdate. `user_id`
    // is always present and is an explicit null when unlinked: on a PATCH that
    // is what CLEARS an existing link (roster.py::update_member), which omitting
    // the key would not do.
    const payload = {
      name: name.trim(),
      role: role.trim() || null,
      email: email.trim() || null,
      color: color.trim() || null,
      // The rate is sent as the string it was typed as (D-11) — no parseFloat,
      // no toFixed; a blank field clears it.
      hourly_rate: hourlyRate.trim() || null,
      user_id: userId === NO_USER ? null : userId,
    }
    const onError = (err: unknown) => {
      toast.error(
        getApiErrorMessage(
          err,
          isEditing
            ? 'Failed to save the team member. Please try again.'
            : 'Failed to add the team member.'
        )
      )
    }

    if (isEditing) {
      updateMutation.mutate(
        { id: member.id, patch: payload },
        {
          onSuccess: (saved) => {
            toast.success(`${saved.name} saved.`)
            onClose()
          },
          onError,
        }
      )
      return
    }
    createMutation.mutate(
      { projectId, payload },
      {
        onSuccess: (created) => {
          toast.success(`${created.name} added to the team.`)
          onClose()
        },
        onError,
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent aria-describedby="member-form-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Team Member' : 'Add Team Member'}</DialogTitle>
          <DialogDescription id="member-form-description">
            The roster is this project’s own, so the same person on another project is a separate
            entry. A platform-user link is optional — an unlinked member is assignable just the
            same.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="member-name">Name</Label>
            <Input
              id="member-name"
              aria-label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Ada Lovelace"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="member-role">Role</Label>
              <Input
                id="member-role"
                aria-label="Role"
                maxLength={60}
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Optional"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="member-email">Email</Label>
              <Input
                id="member-email"
                aria-label="Email"
                maxLength={255}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Optional"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="member-color">Colour</Label>
              <div className="flex items-center gap-2">
                {/* A live preview of what the roster's swatch will show. */}
                <span
                  aria-hidden="true"
                  className="h-5 w-5 shrink-0 rounded border border-border"
                  style={color.trim() ? { backgroundColor: color.trim() } : undefined}
                />
                <Input
                  id="member-color"
                  aria-label="Colour"
                  maxLength={7}
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  placeholder="#4F46E5"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="member-rate">Hourly rate</Label>
              <Input
                id="member-rate"
                aria-label="Hourly rate"
                // Text, not number: the rate is a Decimal that crosses the wire
                // as a string (D-11), and a number input would hand back a float.
                inputMode="decimal"
                value={hourlyRate}
                onChange={(e) => setHourlyRate(e.target.value)}
                placeholder="Optional"
              />
              <p id="member-rate-helper" className="text-xs text-muted-foreground">
                {RATE_HELPER}
              </p>
            </div>
          </div>

          {/* The optional platform-user link — "No platform user" is the default
              and posts a literal null (see handleSubmit). */}
          <div className="space-y-2">
            <Label htmlFor="member-user">Platform user</Label>
            <Select value={userId} onValueChange={setUserId}>
              <SelectTrigger id="member-user" aria-label="Platform user">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_USER}>No platform user</SelectItem>
                {users.map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {platformUserLabel(user)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Optional. An unlinked member is a full collaborator and can be assigned work.
            </p>
          </div>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                {isEditing ? 'Saving…' : 'Adding…'}
              </>
            ) : isEditing ? (
              'Save Member'
            ) : (
              'Add to Team'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
