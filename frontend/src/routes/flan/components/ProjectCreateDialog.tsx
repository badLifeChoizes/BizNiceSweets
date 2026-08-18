// ABOUTME: Create-a-project dialog (FLAN-01.1) — name (required), optional key prefix,
// ABOUTME: category, currency, start/gate dates and description, then POST /flan/projects.
// ABOUTME: Success invalidates the project list, toasts and closes; a 4xx keeps the dialog
// ABOUTME: open and surfaces the server's own `detail` (a refused key prefix is a 422).

/**
 * ProjectCreateDialog — the FLAN "New Project" form (FLAN-01.1).
 *
 * Mirrors routes/crumb/components/LeadCreateDialog.tsx: local field state, one
 * mutation from ../hooks, and `getApiErrorMessage` for the failure path.
 *
 * Only `name` is required. Two fields carry rules worth knowing:
 *
 *   - **`key_prefix` is optional.** Left blank, the server derives it from the
 *     name ("Crisis Simulator" → "CRIS", D-V5P1-2), which is why the payload
 *     sends `null` rather than an empty string — the empty string would fail the
 *     schema's `^[A-Za-z][A-Za-z0-9]{0,9}$` pattern with a 422. Supplied values
 *     are uppercased so hand-typed prefixes read like derived ones do.
 *   - **Duplicate project names are legal** (FLAN-01.1), so there is deliberately
 *     no client-side uniqueness check here — two projects may share a name and
 *     are told apart by their ids.
 *
 * `category` is the prototype's classification (work | personal | client) and is
 * NULL when unclassified, so the Select's "None" option sends `null`.
 *
 * Every key in the POST body exists in the backend's `ProjectCreate` schema
 * (name, key_prefix, category, description, currency, start_date, gate_date);
 * `tags` is omitted, which the schema defaults to an empty list.
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
import { useCreateProject } from '../hooks'

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

/** Currency default — matches the schema's `currency: str = "USD"`. */
const DEFAULT_CURRENCY = 'USD'

// ─── Props ───────────────────────────────────────────────────────────────────

interface ProjectCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ProjectCreateDialog({ open, onOpenChange }: ProjectCreateDialogProps) {
  const [name, setName] = useState('')
  const [keyPrefix, setKeyPrefix] = useState('')
  const [category, setCategory] = useState(NO_CATEGORY)
  const [currency, setCurrency] = useState(DEFAULT_CURRENCY)
  const [startDate, setStartDate] = useState('')
  const [gateDate, setGateDate] = useState('')
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!open) return
    setName('')
    setKeyPrefix('')
    setCategory(NO_CATEGORY)
    setCurrency(DEFAULT_CURRENCY)
    setStartDate('')
    setGateDate('')
    setDescription('')
  }, [open])

  const createMutation = useCreateProject()
  const canSubmit = name.trim() !== ''
  const isSaving = createMutation.isPending

  function handleSubmit() {
    if (!canSubmit) return
    createMutation.mutate(
      {
        name: name.trim(),
        // Blank means "derive it from the name" (D-V5P1-2) — null, never ''.
        key_prefix: keyPrefix.trim() ? keyPrefix.trim().toUpperCase() : null,
        category: category === NO_CATEGORY ? null : category,
        description: description.trim() || null,
        currency: currency.trim().toUpperCase() || DEFAULT_CURRENCY,
        start_date: startDate || null,
        gate_date: gateDate || null,
      },
      {
        onSuccess: (project) => {
          toast.success(`Project “${project.name}” created.`)
          onOpenChange(false)
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, 'Failed to create the project. Please try again.'))
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby="project-create-description" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
          <DialogDescription id="project-create-description">
            Only a name is required. Leave the key prefix blank to have it derived from the name —
            it can be changed until the project’s first task exists.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="project-name">Name</Label>
            <Input
              id="project-name"
              aria-label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Crisis Simulator"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="project-key-prefix">Key prefix</Label>
            <Input
              id="project-key-prefix"
              aria-label="Key prefix"
              value={keyPrefix}
              onChange={(e) => setKeyPrefix(e.target.value)}
              maxLength={10}
              placeholder="Optional — derived from the name when blank"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="project-category">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="project-category" aria-label="Category">
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
              <Label htmlFor="project-currency">Currency</Label>
              <Input
                id="project-currency"
                aria-label="Currency"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                maxLength={3}
                placeholder="USD"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="project-start-date">Start date</Label>
              <Input
                id="project-start-date"
                aria-label="Start date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-gate-date">Gate date</Label>
              <Input
                id="project-gate-date"
                aria-label="Gate date"
                type="date"
                value={gateDate}
                onChange={(e) => setGateDate(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="project-description">Description</Label>
            <Input
              id="project-description"
              aria-label="Description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional"
            />
          </div>
        </div>

        <DialogFooter className="flex gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleSubmit} disabled={isSaving || !canSubmit}>
            {isSaving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Creating…
              </>
            ) : (
              'Create Project'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
