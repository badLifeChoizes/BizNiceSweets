// ABOUTME: FLAN sub-navigation (mirrors GelatoNav) — a per-project tab strip
// ABOUTME: (Phases / Tasks / Team) plus a project switcher Select and a link back
// ABOUTME: to the projects list. The active project is the URL, never local state.

/**
 * FlanNav — sub-navigation for the FLAN (project management) module screens.
 *
 * The left sidebar only exposes the FLAN module root (which redirects to the
 * projects list), so this strip lets users move between one project's screens
 * without typing URLs. Mirrors routes/gelato/components/GelatoNav.tsx and adds
 * the project switcher FLAN-01.6 calls for.
 *
 * **The active project is URL-scoped (D-V5P1-3).** This component holds no
 * "current project" state — no useState, no context, no store. It reads
 * `useParams().projectId` for its value and `navigate()`s when the switcher
 * changes, which is what makes "no view mixes two projects' data" structural:
 * a screen can only ever be handed the one id its URL carries.
 *
 * Switching preserves the section the user is on — picking another project from
 * `/flan/projects/A/tasks` lands on `/flan/projects/B/tasks`, not back at
 * phases — so the section is derived from the pathname, not defaulted.
 *
 * Rendered at the top of each FLAN screen. Uses NavLink so the active screen is
 * highlighted automatically from the current route.
 */
import { Link, NavLink, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { cn } from '@/lib/utils'
import { useProjects } from '../hooks'

const SECTIONS = ['phases', 'tasks', 'team'] as const

type Section = (typeof SECTIONS)[number]

const TABS: Array<{ section: Section; label: string }> = [
  { section: 'phases', label: 'Phases' },
  { section: 'tasks', label: 'Tasks' },
  { section: 'team', label: 'Team' },
]

/**
 * The section segment of `/flan/projects/:projectId/:section`, falling back to
 * Phases for any path that carries none (the module's default screen).
 */
function sectionFromPath(pathname: string): Section {
  const segment = pathname.split('/')[4]
  return SECTIONS.includes(segment as Section) ? (segment as Section) : 'phases'
}

export function FlanNav() {
  const { projectId } = useParams<{ projectId: string }>()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { data: projects = [] } = useProjects()

  const section = sectionFromPath(pathname)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Link
          to="/flan/projects"
          className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          All Projects
        </Link>
        {/* Switching only rewrites the project segment — same section, no state. */}
        <Select
          value={projectId ?? undefined}
          onValueChange={(id) => navigate(`/flan/projects/${id}/${section}`)}
        >
          <SelectTrigger id="flan-project" aria-label="Project" className="w-64">
            <SelectValue placeholder="Select a project" />
          </SelectTrigger>
          <SelectContent>
            {projects.map((project) => (
              <SelectItem key={project.id} value={project.id}>
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {projectId && (
        <nav className="flex gap-1 border-b border-border" aria-label="FLAN sections">
          {TABS.map((tab) => (
            <NavLink
              key={tab.section}
              to={`/flan/projects/${projectId}/${tab.section}`}
              className={({ isActive }) =>
                cn(
                  '-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  )
}
