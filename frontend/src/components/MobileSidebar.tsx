/**
 * MobileSidebar — Sheet drawer for narrow-screen navigation (D-01).
 *
 * Wraps Sidebar in a shadcn Sheet with side="left" and w-64 p-0.
 * Open state is controlled by AppShell — the hamburger in Topbar and
 * this Sheet share one open/onOpenChange pair via AppShell state.
 *
 * Passes onNavigate to Sidebar so clicking a nav item closes the drawer.
 *
 * Accessibility: Sheet provides aria-labelledby/aria-describedby via shadcn defaults.
 */

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Sidebar } from '@/components/Sidebar'
import type { ModuleRecord } from '@/hooks/useModules'

interface MobileSidebarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  visibleModules: ModuleRecord[]
}

export function MobileSidebar({ open, onOpenChange, visibleModules }: MobileSidebarProps) {
  function handleNavigate() {
    onOpenChange(false)
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        className="w-64 p-0"
        aria-labelledby="mobile-nav-title"
        aria-describedby="mobile-nav-description"
      >
        <SheetHeader className="px-3 pt-4 pb-2 border-b">
          <SheetTitle id="mobile-nav-title" className="text-sm font-semibold">
            Navigation
          </SheetTitle>
          <SheetDescription id="mobile-nav-description" className="sr-only">
            Module navigation menu
          </SheetDescription>
        </SheetHeader>

        <Sidebar visibleModules={visibleModules} onNavigate={handleNavigate} />
      </SheetContent>
    </Sheet>
  )
}
