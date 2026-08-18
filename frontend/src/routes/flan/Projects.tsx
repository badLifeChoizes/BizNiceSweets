// ABOUTME: FLAN Projects list screen (/flan/projects) — a table of projects (name,
// ABOUTME: category, currency, start/gate date, key prefix, archived badge), a
// ABOUTME: "Show archived" switch, create/edit dialogs and a soft-archive action behind a
// ABOUTME: confirmation. Rows navigate to /flan/projects/:id/phases (FLAN-01.1, FLAN-01.6).

/**
 * Projects screen — FLAN's top-level list (/flan/projects).
 *
 * Layout: p-8 space-y-6 (matches the CRUMB Leads / GELATO Bins list pattern).
 *
 * Table columns: Name | Key prefix | Category | Currency | Start | Gate | Status
 *                | Actions
 *
 * Three project rules show through the UI here:
 *
 *   - **Archiving is a soft delete** (FLAN-01.1). The archive action confirms
 *     first, and its copy says the project keeps its data and stays readable —
 *     only writes are refused afterwards. Archived projects are hidden until the
 *     Show-archived Switch drives `useProjects(includeArchived)`, which sends
 *     `include_archived` to the server; the filtering is the server's, not a
 *     client-side `.filter()`.
 *   - **`key_prefix` is a real, stored value** (D-V5P1-2) — the column renders
 *     the project's own prefix, which is what every task key under it is built
 *     from. It is not derived on the client and never re-derived from the name.
 *   - **Duplicate names are legal**, so nothing here dedupes or warns; rows are
 *     keyed by id.
 *
 * Row click navigates to that project's phases — the URL is the active project
 * (D-V5P1-3), so no "current project" state lives on this screen either.
 *
 * The row actions cover the rest of FLAN-01.1's verbs: **Open** (view), **Edit**
 * and **Archive**. Edit and Archive are offered on active projects only —
 * `require_writable_project` refuses every write inside an archived project with
 * a 422, so offering either there would only ever produce an error toast.
 *
 * Server 4xx from create and edit surface inside their own dialogs (a refused
 * `key_prefix` change is a 422 from PATCH, D-V5P1-2); archive failures surface
 * here through `getApiErrorMessage` + `toast.error`, so a refusal is reported in
 * the server's own words rather than a generic message.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, MoreHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
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
import { ProjectCreateDialog } from './components/ProjectCreateDialog'
import { ProjectEditDialog } from './components/ProjectEditDialog'
import { useArchiveProject, useProjects } from './hooks'
import type { Project } from './hooks'

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Format a date-only ISO string (`2026-01-05`) for display.
 *
 * The `T00:00:00` suffix parses the value in the LOCAL zone; `new Date('2026-01-05')`
 * would be UTC midnight and could render as the previous day west of Greenwich.
 */
function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return iso
  }
}

/** Category → display label; NULL means unclassified. */
function formatCategory(category: string | null): string {
  if (!category) return '—'
  return category.charAt(0).toUpperCase() + category.slice(1)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

/** Active / Archived badge — colour AND text together, never colour alone. */
function StatusBadge({ active }: { active: boolean }) {
  return active ? (
    <Badge variant="outline" className="border-green-300 bg-green-50 text-green-700">
      Active
    </Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      Archived
    </Badge>
  )
}

/**
 * Archive confirmation — a soft delete, so the copy says so.
 *
 * Mirrors syerp/components/StockLocationArchiveDialog.tsx; the mutation lives in
 * ../hooks (`useArchiveProject`), which invalidates the project list on success.
 */
function ProjectArchiveDialog({
  open,
  project,
  onClose,
}: {
  open: boolean
  project: Project | null
  onClose: () => void
}) {
  const archiveMutation = useArchiveProject()
  const isArchiving = archiveMutation.isPending

  function handleConfirm() {
    if (!project) return
    archiveMutation.mutate(project.id, {
      onSuccess: () => {
        toast(`Project “${project.name}” archived.`)
        onClose()
      },
      onError: (err) => {
        toast.error(getApiErrorMessage(err, 'Failed to archive the project. Please try again.'))
      },
    })
  }

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        aria-labelledby="project-archive-title"
        aria-describedby="project-archive-description"
      >
        <DialogHeader>
          <DialogTitle id="project-archive-title">Archive project?</DialogTitle>
          <DialogDescription id="project-archive-description">
            {project
              ? `${project.name} keeps all of its phases, tasks and team, and stays readable — only writes inside it are refused. It is hidden from this list until "Show archived" is on.`
              : ''}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isArchiving}>
            Keep Project
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isArchiving}
            aria-label={project ? `Archive ${project.name}` : 'Archive project'}
          >
            {isArchiving ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Archiving…
              </>
            ) : (
              'Archive Project'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Projects() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [editProject, setEditProject] = useState<Project | null>(null)
  const [archiveProject, setArchiveProject] = useState<Project | null>(null)

  const { data: projects = [], isLoading, isError } = useProjects(includeArchived)

  return (
    <div className="p-8 space-y-6">
      <FlanNav />

      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Projects</h1>
        <p className="text-base font-normal text-muted-foreground">
          Every phase, task and team member belongs to one project. Open a project to work on its
          phases.
        </p>
      </div>

      {/* Toolbar: show-archived toggle + create */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Switch
            id="project-show-archived"
            checked={includeArchived}
            onCheckedChange={setIncludeArchived}
          />
          <Label htmlFor="project-show-archived" className="text-sm text-muted-foreground">
            Show archived
          </Label>
        </div>
        <Button variant="default" className="ml-auto" onClick={() => setCreateOpen(true)}>
          New Project
        </Button>
      </div>

      {/* Projects table / loading / empty states */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="text-center py-12">
          <p className="text-sm text-muted-foreground">
            Failed to load projects. Check your connection and refresh the page.
          </p>
        </div>
      ) : projects.length === 0 ? (
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No projects yet</p>
          <p className="text-sm text-muted-foreground">Create your first project to get started.</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Key prefix</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Currency</TableHead>
              <TableHead>Start</TableHead>
              <TableHead>Gate</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {projects.map((project) => (
              <TableRow
                key={project.id}
                className="h-12 cursor-pointer"
                onClick={() => navigate(`/flan/projects/${project.id}/phases`)}
                aria-label={`Open project ${project.name}`}
              >
                <TableCell className="font-medium">{project.name}</TableCell>
                {/* The project's STORED prefix — every task key under it starts here. */}
                <TableCell className="font-mono text-sm">{project.key_prefix}</TableCell>
                <TableCell>{formatCategory(project.category)}</TableCell>
                <TableCell>{project.currency}</TableCell>
                <TableCell>{formatDate(project.start_date)}</TableCell>
                <TableCell>{formatDate(project.gate_date)}</TableCell>
                <TableCell>
                  <StatusBadge active={project.active} />
                </TableCell>
                {/* Row click opens the project, so the actions cell keeps its clicks. */}
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`Project actions for ${project.name}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => navigate(`/flan/projects/${project.id}/phases`)}
                      >
                        Open
                      </DropdownMenuItem>
                      {/* Writes inside an archived project are refused (422). */}
                      {project.active && (
                        <>
                          <DropdownMenuItem onClick={() => setEditProject(project)}>
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => setArchiveProject(project)}
                            className="text-destructive focus:text-destructive"
                          >
                            Archive
                          </DropdownMenuItem>
                        </>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── Create dialog ────────────────────────────────────────────────── */}
      <ProjectCreateDialog open={createOpen} onOpenChange={setCreateOpen} />

      {/* ─── Edit dialog ──────────────────────────────────────────────────── */}
      <ProjectEditDialog
        open={editProject !== null}
        project={editProject}
        onClose={() => setEditProject(null)}
      />

      {/* ─── Archive confirmation ─────────────────────────────────────────── */}
      <ProjectArchiveDialog
        open={archiveProject !== null}
        project={archiveProject}
        onClose={() => setArchiveProject(null)}
      />
    </div>
  )
}
