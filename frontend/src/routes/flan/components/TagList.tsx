// ABOUTME: Read-only tag chips for a FLAN table cell — the display half of the Phase-1
// ABOUTME: tag surface (FLAN-01.1, FLAN-01.3), rendered in the order the API returned.
// ABOUTME: An empty list shows an em-dash so an untagged row reads as untagged rather
// ABOUTME: than as a blank cell.

/**
 * TagList — a row's tags, shown as chips.
 *
 * Mirrors routes/plum/PartDetail.tsx's classification-tag block (secondary
 * Badges in a wrapping flex row, em-dash when there are none), which is the
 * house way of showing an opaque string list.
 *
 * The order is the API's own: a Phase-1 tag is an opaque string (D-V5P1-5), so
 * nothing here sorts, groups, colours or otherwise reads meaning into it.
 */

import { Badge } from '@/components/ui/badge'

interface TagListProps {
  tags: string[]
}

export function TagList({ tags }: TagListProps) {
  if (tags.length === 0) return <span className="text-muted-foreground">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} variant="secondary">
          {tag}
        </Badge>
      ))}
    </div>
  )
}
