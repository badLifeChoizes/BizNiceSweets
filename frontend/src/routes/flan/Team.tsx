// ABOUTME: FLAN Team screen (/flan/projects/:projectId/team) — one project's roster
// ABOUTME: (name, role, email, colour, hourly rate, linked platform user) with add/edit
// ABOUTME: and a remove that CONFIRMS and says the member's assignments will be cleared.
// ABOUTME: The rate cell prints the API's string verbatim — no parseFloat, no toFixed.

/**
 * Team screen — one project's roster, the pool every assignee comes from
 * (FLAN-01.4).
 *
 * Layout: p-8 space-y-6, mirroring routes/flan/Phases.tsx.
 *
 * Table columns: Member | Role | Email | Colour | Hourly rate | Platform user
 *                | Actions
 *
 * Four rules are load-bearing here:
 *
 *   - **The hourly rate is rendered exactly as the API returned it.** It is a
 *     Decimal serialized as a string (D-11), so the backend's `"42.500000"` is
 *     printed as `42.500000`. No `parseFloat`, no `toFixed`, no currency
 *     formatter: every one of those re-rounds the shop's own figure on the
 *     client's terms and makes the screen disagree with the database.
 *   - **Nothing reads that rate in v5.0** (D-V5-2 / D-M5-2). No rollup, report
 *     or endpoint in this release derives a cost from it, and the dialog's own
 *     helper text says so — otherwise a user reasonably assumes a costing
 *     feature exists behind it.
 *   - **A member with no platform user is a full collaborator**, not a
 *     second-class row (roster.py). The link is optional and normally absent;
 *     the column shows an em-dash and the member is listed and assignable
 *     exactly like a linked one.
 *   - **Removal is a SOFT remove that also clears assignments** (D-V5P1-6):
 *     `DELETE /flan/team/{member_id}` sets `active=False` AND deletes the
 *     member's task and phase assignment rows in the same transaction, leaving
 *     the tasks themselves untouched. The confirmation copy names that
 *     consequence, because it is the half of the decision the user cannot see.
 *
 * **There is deliberately no reactivation control and no "show removed"
 * switch** (owner decision at plan review). A removed member stays removed in
 * v5.0: the service has no `reactivate_member`, `TeamMemberUpdate` carries no
 * `active` field and `GET /flan/projects/{id}/team` exposes no
 * `include_removed` query parameter, so there is nothing here to call. The row
 * and its history survive, so a later phase can add one additively.
 *
 * The active project is the URL (D-V5P1-3): `useParams().projectId` scopes every
 * query and mutation here, and no "current project" state exists.
 */

import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Loader2, MoreHorizontal } from 'lucide-react'
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { getApiErrorMessage } from '@/routes/crumb/components/apiError'
import { FlanNav } from './components/FlanNav'
import { MemberDialog } from './components/MemberDialog'
import { platformUserLabel, usePlatformUsers } from './components/platformUsers'
import { useRemoveMember, useTeam } from './hooks'
import type { TeamMember } from './hooks'

// ─── Sub-components ──────────────────────────────────────────────────────────

/**
 * A member's colour: the swatch AND its hex value, never the swatch alone —
 * colour is never the only carrier of information (the house accessibility
 * rule). A member with no colour renders an em-dash.
 */
function ColorSwatch({ color }: { color: string | null }) {
  if (!color) return <span>—</span>
  return (
    <span className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="h-4 w-4 shrink-0 rounded border border-border"
        style={{ backgroundColor: color }}
      />
      <span className="font-mono text-xs">{color}</span>
    </span>
  )
}

/**
 * Remove confirmation — a SOFT remove that clears the member's assignments
 * (D-V5P1-6).
 *
 * The copy names all three consequences, because only the first is visible from
 * the roster: the member leaves the team, their task and phase assignments are
 * cleared, and the tasks themselves are left intact. It also says the removal
 * cannot be undone — v5.0 has no reactivation path, by decision.
 */
function MemberRemoveDialog({
  open,
  projectId,
  member,
  onClose,
}: {
  open: boolean
  projectId: string
  member: TeamMember | null
  onClose: () => void
}) {
  const removeMutation = useRemoveMember()
  const isRemoving = removeMutation.isPending

  function handleConfirm() {
    if (!member) return
    removeMutation.mutate(
      { id: member.id, projectId },
      {
        onSuccess: () => {
          toast(`${member.name} was removed from the team and their assignments were cleared.`)
          onClose()
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to remove the member. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        aria-labelledby="member-remove-title"
        aria-describedby="member-remove-description"
      >
        <DialogHeader>
          <DialogTitle id="member-remove-title">Remove member?</DialogTitle>
          <DialogDescription id="member-remove-description">
            {member
              ? `Removing ${member.name} clears their task and phase assignments — the tasks ` +
                `themselves are left intact, and their history is kept so past references still ` +
                `resolve. They can no longer be assigned work on this project, and this cannot ` +
                `be undone in this release.`
              : ''}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isRemoving}>
            Keep Member
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isRemoving}
            aria-label={member ? `Remove ${member.name}` : 'Remove member'}
          >
            {isRemoving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Removing…
              </>
            ) : (
              'Remove Member'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Team() {
  // The URL is the active project (D-V5P1-3) — no "current project" state here.
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [createOpen, setCreateOpen] = useState(false)
  const [editMember, setEditMember] = useState<TeamMember | null>(null)
  const [removeMember, setRemoveMember] = useState<TeamMember | null>(null)

  // The roster the API returns: active members only, in its own order (name,
  // then created_at). Removed members are excluded server-side and there is no
  // parameter here to ask for them.
  const { data: team = [], isLoading, isError } = useTeam(projectId)
  // Labels for the linked-user column. A non-admin cannot list users (403), so
  // this legitimately comes back empty — the column falls back to the raw id.
  const { data: users = [] } = usePlatformUsers()
  const userLabels = new Map(users.map((user) => [user.id, platformUserLabel(user)]))

  return (
    <div className="p-8 space-y-6">
      <FlanNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Team</h1>
        <p className="text-base font-normal text-muted-foreground">
          This project’s roster — everyone who can be assigned its work. A platform-user link is
          optional, and the roster belongs to this project alone.
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center">
        <Button variant="default" className="ml-auto" onClick={() => setCreateOpen(true)}>
          Add Member
        </Button>
      </div>

      {/* Roster table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load the team. Check your connection and refresh the page.
          </p>
        </div>
      ) : team.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No one on the team yet</p>
          <p className="text-sm text-muted-foreground">
            Add the first member so this project’s work can be assigned.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Member</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Colour</TableHead>
              <TableHead>Hourly rate</TableHead>
              <TableHead>Platform user</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {/* Server order (name, then created_at) — never re-sorted here. */}
            {team.map((member) => (
              <TableRow key={member.id} className="h-12" aria-label={`Member ${member.name}`}>
                <TableCell className="font-medium">{member.name}</TableCell>
                <TableCell>{member.role ?? '—'}</TableCell>
                <TableCell>{member.email ?? '—'}</TableCell>
                <TableCell>
                  <ColorSwatch color={member.color} />
                </TableCell>
                {/* The API's own Decimal string, printed verbatim (D-11). Never
                    parseFloat'd, never toFixed'd, never currency-formatted. */}
                <TableCell className="font-mono text-sm">{member.hourly_rate ?? '—'}</TableCell>
                {/* An unlinked member is the normal case, not a gap. */}
                <TableCell>
                  {member.user_id ? (userLabels.get(member.user_id) ?? member.user_id) : '—'}
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Member actions for ${member.name}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setEditMember(member)}>
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setRemoveMember(member)}
                        className="text-destructive focus:text-destructive"
                      >
                        Remove
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── Add / edit dialog ────────────────────────────────────────────── */}
      <MemberDialog
        open={createOpen || editMember !== null}
        projectId={projectId}
        member={editMember}
        onClose={() => {
          setCreateOpen(false)
          setEditMember(null)
        }}
      />

      {/* ─── Remove confirmation ──────────────────────────────────────────── */}
      <MemberRemoveDialog
        open={removeMember !== null}
        projectId={projectId}
        member={removeMember}
        onClose={() => setRemoveMember(null)}
      />
    </div>
  )
}
