// ABOUTME: Minimal chip-style tag editor shared by the FLAN project dialogs and the task
// ABOUTME: sheet (FLAN-01.1, FLAN-01.3). A Phase-1 tag is an OPAQUE STRING (D-V5P1-5):
// ABOUTME: no facets, no colours, no vocabulary — the input trims, drops blanks and
// ABOUTME: de-duplicates CASE-SENSITIVELY, exactly as schemas.py::_normalize_tags does.

/**
 * TagInput — the whole of FLAN's Phase-1 tag editing surface.
 *
 * Props:
 *   id: string                        — the input's id (labels are per-form)
 *   label: string                     — visible Label text and the input's aria-label
 *   value: string[]                   — the tags held right now
 *   onChange: (tags: string[]) => void — called with the COMPLETE new list
 *   placeholder?: string              — input placeholder
 *
 * Deliberately small, and it stays that way until FLAN-04: **a Phase-1 tag is an
 * opaque string** (D-V5P1-5). There is no `Facet:Value` parsing, no reserved
 * facet, no colour mapping and no autocomplete against a taxonomy — those are
 * next phase's, and building them here would create a shape the backend has no
 * rules for.
 *
 * The client-side rules are exactly the ones `schemas.py::_normalize_tags`
 * applies, so a tag that reaches the wire is already one the schema accepts:
 *
 *   - **trimmed**, and a blank one is never committed (the schema 422s
 *     `"A tag must not be empty or whitespace-only."`);
 *   - **de-duplicated case-sensitively** — `"Client"` and `"client"` are two
 *     distinct tags in Phase 1, so only an exact repeat is dropped;
 *   - **capped at 60 characters**, the width of `flan_project_tag.tag` /
 *     `flan_task_tag.tag`.
 *
 * Committing is explicit: Enter or a comma turns the draft into chips (a pasted
 * `"red, blue"` splits on the commas), and each chip carries its own × button.
 * The draft is NOT committed on blur — a half-typed tag is not a tag, and
 * guessing at one would put a value in the body the user never confirmed.
 *
 * The caller owns the list; this component holds only the uncommitted draft.
 * Note the write semantics on the other side: supplying `tags` in a PATCH
 * REPLACES the whole set, so a form using this must seed `value` from the row.
 */

import { useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

// ─── Constants ───────────────────────────────────────────────────────────────

/** The `flan_project_tag.tag` / `flan_task_tag.tag` column width (D-V5P1-5). */
const MAX_TAG_LENGTH = 60

// ─── Props ───────────────────────────────────────────────────────────────────

interface TagInputProps {
  id: string
  label: string
  value: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
}

// ─── Main component ──────────────────────────────────────────────────────────

export function TagInput({ id, label, value, onChange, placeholder }: TagInputProps) {
  const [draft, setDraft] = useState('')

  /**
   * Turn the draft into chips. Splits on commas so a pasted "red, blue" adds
   * two, then applies the schema's own rules: trim, drop the blanks, keep the
   * first of any exact repeat (case-sensitively — D-V5P1-5).
   */
  function commitDraft(raw: string) {
    const next = [...value]
    for (const part of raw.split(',')) {
      const tag = part.trim()
      if (!tag || next.includes(tag)) continue
      next.push(tag)
    }
    setDraft('')
    // Nothing survived the trim/de-dupe → nothing to tell the caller about.
    if (next.length !== value.length) onChange(next)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter' && event.key !== ',') return
    // Enter would submit an enclosing form; the comma is the separator itself.
    event.preventDefault()
    commitDraft(draft)
  }

  function removeTag(tag: string) {
    onChange(value.filter((existing) => existing !== tag))
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((tag) => (
            <Badge key={tag} variant="secondary" className="gap-1">
              {tag}
              <button
                type="button"
                aria-label={`Remove tag ${tag}`}
                onClick={() => removeTag(tag)}
                className="rounded-full text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" aria-hidden="true" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <Input
        id={id}
        aria-label={label}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        maxLength={MAX_TAG_LENGTH}
        placeholder={placeholder ?? 'Type a tag, then press Enter'}
      />
      <p className="text-xs text-muted-foreground">
        Press Enter or comma to add a tag. Tags are plain labels — “Client” and “client” are two
        different tags.
      </p>
    </div>
  )
}
