// ABOUTME: Edit-a-project dialog (FLAN-01.1, the "edit" verb) — name, key prefix, category,
// ABOUTME: currency, start/gate dates and description seeded from the row, then PATCH
// ABOUTME: /flan/projects/{id}. The body carries only ProjectUpdate keys — never `id`, never
// ABOUTME: `active`. A refused key-prefix change comes back 422 and is toasted verbatim.

/**
 * ProjectEditDialog — the FLAN "Edit project" form (FLAN-01.1).
 *
 * Mirrors ./ProjectCreateDialog.tsx (local field state, one mutation from
 * ../hooks, `getApiErrorMessage` on the failure path); the differences are all
 * consequences of this being a PATCH rather than a POST:
 *
 *   - **The form seeds from the row's own values** on every open, so what the
 *     user sees is what the project currently holds. A blank-opening edit form
 *     silently discards whatever it fails to show.
 *   - **`key_prefix` is offered for editing, unconditionally** (D-V5P1-2). It is
 *     editable only while the project has no task, and the server owns that
 *     rule: `update_project` answers a prefix change on a project with tasks
 *     with a **422** naming the project and its current prefix. Predicting the
 *     lock here would need a task count the list endpoint does not return, and
 *     would drift from the server the first time the rule moved — so the user is
 *     allowed to try and the server's own `detail` is what they read back.
 *   - **The payload never carries `id` or `active`.** `ProjectUpdate` has no
 *     such fields: the project id is immutable and archiving is its own endpoint
 *     (POST /flan/projects/{id}/archive), which the Projects screen calls.
 *   - **`tags` is omitted**, because this form has no tag editor and supplying
 *     `tags` REPLACES the project's whole tag set — an omitted key leaves it alone.
 *
 * Name, key prefix and currency back NOT NULL columns, so submit stays disabled
 * while any of them is blank: `update_project` skips an explicit null aimed at
 * one of those columns, which would make a "clear this field" click look like it
 * saved when nothing happened. Clearing an OPTIONAL field is legitimate and does
 * work — category, description and both dates cross as null.
 */

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { getApiErrorMessage } from '@/routes/crumb/components/apiError'
import { useUpdateProject } from '../hooks'
import type { Project } from '../hooks'

// ─── Constants ───────────────────────────────────────────────────────────────

/** Sentinel for "unclassified" — Radix forbids an empty SelectItem value. */
const NO_CATEGORY = 'none'

/** Project classifications (flan_project.category; NULL when unclassified). */
const CATEGORIES: Array<{ value: string; label: string }> = [
  { value: NO_CATEGORY, label: 'None' },
  { value: 'work', label: 'Work' },
  { value: 'personal', label: 'Personal' },
  { value: 'client', label: 'Client' },
]

// ─── Props ───────────────────────────────────────────────────────────────────

interface ProjectEditDialogProps {
  open: boolean
  /** The row being edited; null while the dialog is closed. */
  project: Project | null
  onClose: () => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ProjectEditDialog({ open, project, onClose }: ProjectEditDialogProps) {
  const [name, setName] = useState('')
  const [keyPrefix, setKeyPrefix] = useState('')
  const [category, setCategory] = useState(NO_CATEGORY)
  const [currency, setCurrency] = useState('')
  const [startDate, setStartDate] = useState('')
  const [gateDate, setGateDate] = useState('')
  const [description, setDescription] = useState('')

  // Seed on open from the row's OWN values — never a blank form, never defaults.
  useEffect(() => {
    if (!open || !project) return
    setName(project.name)
    setKeyPrefix(project.key_prefix)
    setCategory(project.category ?? NO_CATEGORY)
    setCurrency(project.currency)
    setStartDate(project.start_date ?? '')
    setGateDate(project.gate_date ?? '')
    setDescription(project.description ?? '')
  }, [open, project])

  const updateMutation = useUpdateProject()
  const isSaving = updateMutation.isPending
  // The three NOT NULL columns must stay non-blank; the rest may be cleared.
  const canSubmit =
    name.trim() !== '' && keyPrefix.trim() !== '' && currency.trim() !== '' && project !== null

  function handleSubmit() {
    if (!canSubmit || !project) return
    updateMutation.mutate(
      {
        id: project.id,
        // Every key below exists in the backend's `ProjectUpdate`; `id` and
        // `active` are absent from that schema and so from this body.
        patch: {
          name: name.trim(),
          // Uppercased the way `derive_key_prefix` uppercases, so one project
          // cannot hold both CRIS-1 and cris-1. A 422 here means the project
          // already has tasks (D-V5P1-2) — the server says so in its `detail`.
          key_prefix: keyPrefix.trim().toUpperCase(),
          category: category === NO_CATEGORY ? null : category,
          description: description.trim() || null,
          currency: currency.trim().toUpperCase(),
          start_date: startDate || null,
          gate_date: gateDate || null,
        },
      },
      {
        onSuccess: (saved) => {
          toast.success(`Project “${saved.name}” saved.`)
          onClose()
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to save the project. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent aria-describedby="project-edit-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Project</DialogTitle>
          <DialogDescription id="project-edit-description">
            Name, key prefix and currency are required. The key prefix can only be changed until the
            project’s first task exists — after that the server refuses the change and says so.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="project-edit-name">Name</Label>
            <Input
              id="project-edit-name"
              aria-label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="project-edit-key-prefix">Key prefix</Label>
            <Input
              id="project-edit-key-prefix"
              aria-label="Key prefix"
              value={keyPrefix}
              onChange={(e) => setKeyPrefix(e.target.value)}
              maxLength={10}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="project-edit-category">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="project-edit-category" aria-label="Category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-edit-currency">Currency</Label>
              <Input
                id="project-edit-currency"
                aria-label="Currency"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                maxLength={3}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="project-edit-start-date">Start date</Label>
              <Input
                id="project-edit-start-date"
                aria-label="Start date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-edit-gate-date">Gate date</Label>
              <Input
                id="project-edit-gate-date"
                aria-label="Gate date"
                type="date"
                value={gateDate}
                onChange={(e) => setGateDate(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="project-edit-description">Description</Label>
            <Input
              id="project-edit-description"
              aria-label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional"
            />
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
                Saving…
              </>
            ) : (
              'Save Project'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
