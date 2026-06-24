/**
 * Admin User Management screen — UI-SPEC Screen 3.
 *
 * Layout: full-width content area with:
 *   - Page heading "Users" + description
 *   - Toolbar: debounced search input + accent "Create User" button (only accent element)
 *   - Table: Full Name | Email | Role(s) | Status | Actions
 *   - Sheet (side="right"): Create / Edit user form with role Select
 *   - Dialog (destructive): Deactivate user confirmation
 *
 * Data: useQuery for GET /api/v1/auth/users; useMutation for create/edit/deactivate.
 * Search: client-side, debounced 300ms.
 * Accessibility:
 *   - All inputs have Label (htmlFor pairing)
 *   - Dialog/Sheet have aria-labelledby
 *   - Actions trigger has row-scoped aria-label="User actions for {full_name}"
 *   - Deactivate button has aria-label="Deactivate {full_name}"
 *   - Badge uses both color AND text (never color alone)
 */

import { useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MoreHorizontal, Eye, EyeOff, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { apiClient } from '@/api/client'
import { cn } from '@/lib/utils'

// ─── Types ───────────────────────────────────────────────────────────────────

interface UserRole {
  name: string
}

interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  roles: UserRole[]
}

type SheetMode = 'create' | 'edit'

interface SheetState {
  open: boolean
  mode: SheetMode
  user: User | null
}

interface DeactivateState {
  open: boolean
  user: User | null
}

// ─── API helpers ─────────────────────────────────────────────────────────────

function fetchUsers(): Promise<User[]> {
  return apiClient.get<User[]>('/api/v1/auth/users').then((r) => r.data)
}

interface CreatePayload {
  email: string
  full_name: string
  password: string
  role_name: string
}

interface UpdatePayload {
  user_id: string
  full_name?: string
  is_active?: boolean
  role_name?: string
}

function createUser(payload: CreatePayload): Promise<User> {
  return apiClient.post<User>('/api/v1/auth/users', payload).then((r) => r.data)
}

function updateUser({ user_id, ...payload }: UpdatePayload): Promise<User> {
  return apiClient.patch<User>(`/api/v1/auth/users/${user_id}`, payload).then((r) => r.data)
}

// ─── Sub-components ──────────────────────────────────────────────────────────

interface StatusBadgeProps {
  isActive: boolean
}

function StatusBadge({ isActive }: StatusBadgeProps) {
  // Color AND text used together (never color alone) — UI-SPEC accessibility requirement
  if (isActive) {
    return (
      <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-green-50 text-green-600">
        Active
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-gray-100 text-gray-500">
      Inactive
    </span>
  )
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Users() {
  const queryClient = useQueryClient()

  // Search filter (debounced)
  const [searchValue, setSearchValue] = useState('')
  const [searchFilter, setSearchFilter] = useState('')
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value
    setSearchValue(v)
    if (debounceTimer.current) clearTimeout(debounceTimer.current)
    debounceTimer.current = setTimeout(() => setSearchFilter(v), 300)
  }, [])

  // Sheet (Create/Edit)
  const [sheet, setSheet] = useState<SheetState>({ open: false, mode: 'create', user: null })
  const [formFullName, setFormFullName] = useState('')
  const [formEmail, setFormEmail] = useState('')
  const [formPassword, setFormPassword] = useState('')
  const [formRole, setFormRole] = useState('user')
  const [showFormPassword, setShowFormPassword] = useState(false)
  const fullNameRef = useRef<HTMLInputElement>(null)

  // Deactivate dialog
  const [deactivate, setDeactivate] = useState<DeactivateState>({ open: false, user: null })

  // ── Data ──
  const { data: users = [], isLoading: usersLoading } = useQuery<User[], Error>({
    queryKey: ['users'],
    queryFn: fetchUsers,
  })

  const createMutation = useMutation<User, Error, CreatePayload>({
    mutationFn: createUser,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      closeSheet()
    },
  })

  const updateMutation = useMutation<User, Error, UpdatePayload>({
    mutationFn: updateUser,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['users'] })
      closeSheet()
      setDeactivate({ open: false, user: null })
    },
  })

  // ── Sheet helpers ──
  function openCreateSheet() {
    setFormFullName('')
    setFormEmail('')
    setFormPassword('')
    setFormRole('user')
    setShowFormPassword(false)
    setSheet({ open: true, mode: 'create', user: null })
    // Focus moves to Full Name on open (handled by onOpenChange/autoFocus)
  }

  function openEditSheet(user: User) {
    setFormFullName(user.full_name ?? '')
    setFormEmail(user.email)
    setFormPassword('')
    setFormRole(user.roles[0]?.name ?? 'user')
    setShowFormPassword(false)
    setSheet({ open: true, mode: 'edit', user })
  }

  function closeSheet() {
    setSheet((s) => ({ ...s, open: false }))
  }

  function handleSheetOpenChange(open: boolean) {
    if (!open) closeSheet()
    else if (sheet.mode === 'create') {
      // Auto-focus Full Name when sheet opens
      setTimeout(() => fullNameRef.current?.focus(), 100)
    }
  }

  // Focus on Full Name when sheet opens
  function handleSheetAnimationEnd() {
    if (sheet.open) {
      setTimeout(() => fullNameRef.current?.focus(), 0)
    }
  }

  function handleSaveChanges() {
    if (sheet.mode === 'create') {
      createMutation.mutate({
        email: formEmail,
        full_name: formFullName,
        password: formPassword,
        role_name: formRole,
      })
    } else if (sheet.user) {
      updateMutation.mutate({
        user_id: sheet.user.id,
        full_name: formFullName,
        role_name: formRole,
      })
    }
  }

  // ── Deactivate helpers ──
  function openDeactivateDialog(user: User) {
    setDeactivate({ open: true, user })
  }

  function handleDeactivate() {
    if (deactivate.user) {
      updateMutation.mutate({ user_id: deactivate.user.id, is_active: false })
    }
  }

  function handleActivate(user: User) {
    updateMutation.mutate({ user_id: user.id, is_active: true })
  }

  // ── Filtered users ──
  const filteredUsers = users.filter((u) => {
    if (!searchFilter) return true
    const q = searchFilter.toLowerCase()
    return (
      (u.full_name ?? '').toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q)
    )
  })

  const isSaving = createMutation.isPending || updateMutation.isPending

  // ── Render ──
  return (
    <div className="p-8 space-y-6">
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">Users</h1>
        <p className="text-base font-normal text-muted-foreground">
          Manage who can access this installation.
        </p>
      </div>

      {/* Toolbar: Search + Create User */}
      <div className="flex items-center gap-4">
        <Input
          placeholder="Search users…"
          value={searchValue}
          onChange={handleSearchChange}
          className="max-w-xs"
          aria-label="Search users"
        />
        {/* "Create User" is the ONLY accent/default button on this screen */}
        <Button variant="default" onClick={openCreateSheet} className="ml-auto">
          Create User
        </Button>
      </div>

      {/* Users table */}
      {usersLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : filteredUsers.length === 0 ? (
        // Empty state
        <div className="text-center py-12 space-y-2">
          <p className="text-base font-semibold text-foreground">No users found</p>
          <p className="text-sm text-muted-foreground">
            No users match your search. Clear the filter or create a new user.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Full Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role(s)</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-12">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredUsers.map((user) => (
              <TableRow key={user.id} className="h-12">
                <TableCell className="font-medium">
                  {user.full_name ?? '—'}
                </TableCell>
                <TableCell>{user.email}</TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {user.roles.map((r) => (
                      <Badge key={r.name} variant="outline">
                        {r.name}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <StatusBadge isActive={user.is_active} />
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-11 w-11"
                        aria-label={`User actions for ${user.full_name ?? user.email}`}
                      >
                        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                        <span className="sr-only">Open actions menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => openEditSheet(user)}>
                        Edit
                      </DropdownMenuItem>
                      {user.is_active ? (
                        <DropdownMenuItem
                          onClick={() => openDeactivateDialog(user)}
                          className="text-destructive focus:text-destructive"
                        >
                          Deactivate User
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem onClick={() => handleActivate(user)}>
                          Activate
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── Create / Edit Sheet ─────────────────────────────────────────────── */}
      <Sheet open={sheet.open} onOpenChange={handleSheetOpenChange}>
        <SheetContent
          side="right"
          onAnimationEnd={handleSheetAnimationEnd}
          aria-labelledby="sheet-title"
          aria-describedby="sheet-description"
        >
          <SheetHeader>
            <SheetTitle id="sheet-title">
              {sheet.mode === 'create' ? 'Create User' : 'Edit User'}
            </SheetTitle>
            <SheetDescription id="sheet-description">
              {sheet.mode === 'create'
                ? 'Fill in the details to create a new user account.'
                : 'Update the user account details.'}
            </SheetDescription>
          </SheetHeader>

          <div className="py-6 space-y-4">
            {/* Full Name */}
            <div className="space-y-2">
              <Label htmlFor="sheet-full-name">Full Name</Label>
              <Input
                id="sheet-full-name"
                ref={fullNameRef}
                value={formFullName}
                onChange={(e) => setFormFullName(e.target.value)}
                placeholder="Jane Doe"
              />
            </div>

            {/* Email */}
            <div className="space-y-2">
              <Label htmlFor="sheet-email">Email</Label>
              <Input
                id="sheet-email"
                type="email"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                placeholder="jane@example.com"
                disabled={sheet.mode === 'edit'} // email is not editable post-create
              />
            </div>

            {/* Password — create only */}
            {sheet.mode === 'create' && (
              <div className="space-y-2">
                <Label htmlFor="sheet-password">Password</Label>
                <div className="relative">
                  <Input
                    id="sheet-password"
                    type={showFormPassword ? 'text' : 'password'}
                    value={formPassword}
                    onChange={(e) => setFormPassword(e.target.value)}
                    className="pr-10"
                    placeholder="Set initial password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowFormPassword((v) => !v)}
                    aria-label={showFormPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                  >
                    {showFormPassword ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Role */}
            <div className="space-y-2">
              <Label htmlFor="sheet-role">Role</Label>
              <Select value={formRole} onValueChange={setFormRole}>
                <SelectTrigger id="sheet-role">
                  <SelectValue placeholder="Select a role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">admin</SelectItem>
                  <SelectItem value="user">user</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <SheetFooter className={cn('flex gap-2 pt-4')}>
            <Button
              variant="outline"
              onClick={closeSheet}
              disabled={isSaving}
            >
              Discard Changes
            </Button>
            <Button
              variant="default"
              onClick={handleSaveChanges}
              disabled={isSaving}
            >
              {isSaving ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" />
                  Saving…
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* ─── Deactivate Confirmation Dialog ──────────────────────────────────── */}
      <Dialog
        open={deactivate.open}
        onOpenChange={(open) => !open && setDeactivate({ open: false, user: null })}
      >
        <DialogContent aria-labelledby="deactivate-title" aria-describedby="deactivate-description">
          <DialogHeader>
            <DialogTitle id="deactivate-title">Deactivate user?</DialogTitle>
            <DialogDescription id="deactivate-description">
              {deactivate.user
                ? `This will immediately end all active sessions for ${deactivate.user.full_name ?? deactivate.user.email}. They will not be able to log in until reactivated.`
                : ''}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeactivate({ open: false, user: null })}
              disabled={isSaving}
            >
              Keep User Active
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeactivate}
              disabled={isSaving}
              aria-label={
                deactivate.user
                  ? `Deactivate ${deactivate.user.full_name ?? deactivate.user.email}`
                  : 'Deactivate user'
              }
            >
              {isSaving ? (
                <>
                  <Loader2 className="animate-spin" aria-hidden="true" />
                  Deactivating…
                </>
              ) : (
                'Deactivate User'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
