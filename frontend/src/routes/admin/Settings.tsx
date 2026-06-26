/**
 * Settings — admin System Settings form (D-11, CORE-06).
 *
 * Two Card sections:
 *   1. Company Identity — Company Name (Input, required)
 *   2. Locale Defaults  — Currency, Date Format, Timezone, Units (Select)
 *
 * On save: PATCHes only changed settings via /api/v1/core/settings/{key},
 * then invalidates ['core', 'settings'].
 *
 * Loading: inputs disabled + placeholder; submit button disabled.
 * Success toast: "Settings saved."
 * Error toast: "Failed to save settings. Please try again."
 *
 * Accessibility: every Label is paired with its Input/Select via htmlFor + id.
 * Typography: font-semibold (600) for labels/headings; font-normal (400) for body.
 */

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useSettings, type SettingRecord } from '@/hooks/useSettings'
import { apiClient } from '@/api/client'

// ─── Option lists for locale defaults ────────────────────────────────────────

const CURRENCY_OPTIONS = [
  { value: 'USD', label: 'USD — US Dollar' },
  { value: 'EUR', label: 'EUR — Euro' },
  { value: 'GBP', label: 'GBP — British Pound' },
  { value: 'JPY', label: 'JPY — Japanese Yen' },
  { value: 'CAD', label: 'CAD — Canadian Dollar' },
  { value: 'AUD', label: 'AUD — Australian Dollar' },
]

const DATE_FORMAT_OPTIONS = [
  { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD (ISO 8601)' },
  { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY (US)' },
  { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY (EU)' },
  { value: 'DD-MM-YYYY', label: 'DD-MM-YYYY' },
]

const TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'Eastern Time (US)' },
  { value: 'America/Chicago', label: 'Central Time (US)' },
  { value: 'America/Denver', label: 'Mountain Time (US)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (US)' },
  { value: 'Europe/London', label: 'London (GMT/BST)' },
  { value: 'Europe/Paris', label: 'Central European Time' },
  { value: 'Asia/Tokyo', label: 'Japan Standard Time' },
]

const UNITS_OPTIONS = [
  { value: 'metric', label: 'Metric (kg, mm, L)' },
  { value: 'imperial', label: 'Imperial (lb, in, gal)' },
]

// ─── Helper ───────────────────────────────────────────────────────────────────

function getSettingValue(settings: SettingRecord[], key: string): string {
  return settings.find((s) => s.key === key)?.value ?? ''
}

// ─── Main component ──────────────────────────────────────────────────────────

export function Settings() {
  const queryClient = useQueryClient()
  const { data: settings = [], isLoading } = useSettings()
  const [isSaving, setIsSaving] = useState(false)

  // Form state — initialized from settings data
  const [companyName, setCompanyName] = useState('')
  const [currency, setCurrency] = useState('')
  const [dateFormat, setDateFormat] = useState('')
  const [timezone, setTimezone] = useState('')
  const [units, setUnits] = useState('')

  // Sync form state when settings load
  useEffect(() => {
    if (settings.length > 0) {
      setCompanyName(getSettingValue(settings, 'company.name'))
      setCurrency(getSettingValue(settings, 'locale.currency'))
      setDateFormat(getSettingValue(settings, 'locale.date_format'))
      setTimezone(getSettingValue(settings, 'locale.timezone'))
      setUnits(getSettingValue(settings, 'locale.units'))
    }
  }, [settings])

  async function handleSave() {
    setIsSaving(true)
    try {
      // Build list of changes: only PATCH settings that have changed
      const changes: Array<{ key: string; value: string }> = []

      if (companyName !== getSettingValue(settings, 'company.name')) {
        changes.push({ key: 'company.name', value: companyName })
      }
      if (currency !== getSettingValue(settings, 'locale.currency')) {
        changes.push({ key: 'locale.currency', value: currency })
      }
      if (dateFormat !== getSettingValue(settings, 'locale.date_format')) {
        changes.push({ key: 'locale.date_format', value: dateFormat })
      }
      if (timezone !== getSettingValue(settings, 'locale.timezone')) {
        changes.push({ key: 'locale.timezone', value: timezone })
      }
      if (units !== getSettingValue(settings, 'locale.units')) {
        changes.push({ key: 'locale.units', value: units })
      }

      if (changes.length === 0) {
        toast.success('Settings saved.')
        return
      }

      // PATCH each changed setting
      await Promise.all(
        changes.map(({ key, value }) =>
          apiClient.patch(`/api/v1/core/settings/${key}`, { value }),
        ),
      )

      // Invalidate the settings cache so Topbar company name updates
      await queryClient.invalidateQueries({ queryKey: ['core', 'settings'] })

      toast.success('Settings saved.')
    } catch {
      toast.error('Failed to save settings. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Page heading */}
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-foreground">System Settings</h1>
      </div>

      {/* Card 1: Company Identity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Company Identity</CardTitle>
          <CardDescription className="text-sm font-normal">
            Configure your company name displayed across the application.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="settings-company-name" className="text-sm font-semibold">
              Company Name
            </Label>
            <Input
              id="settings-company-name"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder={isLoading ? 'Loading…' : 'Your company name'}
              disabled={isLoading || isSaving}
              required
            />
          </div>
        </CardContent>
      </Card>

      {/* Card 2: Locale Defaults */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Locale Defaults</CardTitle>
          <CardDescription className="text-sm font-normal">
            Default locale settings used across modules.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Currency */}
          <div className="space-y-2">
            <Label htmlFor="settings-currency" className="text-sm font-semibold">
              Currency
            </Label>
            <Select
              value={currency}
              onValueChange={setCurrency}
              disabled={isLoading || isSaving}
            >
              <SelectTrigger id="settings-currency">
                <SelectValue placeholder={isLoading ? 'Loading…' : 'Select currency'} />
              </SelectTrigger>
              <SelectContent>
                {CURRENCY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date Format */}
          <div className="space-y-2">
            <Label htmlFor="settings-date-format" className="text-sm font-semibold">
              Date Format
            </Label>
            <Select
              value={dateFormat}
              onValueChange={setDateFormat}
              disabled={isLoading || isSaving}
            >
              <SelectTrigger id="settings-date-format">
                <SelectValue placeholder={isLoading ? 'Loading…' : 'Select date format'} />
              </SelectTrigger>
              <SelectContent>
                {DATE_FORMAT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Timezone */}
          <div className="space-y-2">
            <Label htmlFor="settings-timezone" className="text-sm font-semibold">
              Timezone
            </Label>
            <Select
              value={timezone}
              onValueChange={setTimezone}
              disabled={isLoading || isSaving}
            >
              <SelectTrigger id="settings-timezone">
                <SelectValue placeholder={isLoading ? 'Loading…' : 'Select timezone'} />
              </SelectTrigger>
              <SelectContent>
                {TIMEZONE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Units */}
          <div className="space-y-2">
            <Label htmlFor="settings-units" className="text-sm font-semibold">
              Units
            </Label>
            <Select
              value={units}
              onValueChange={setUnits}
              disabled={isLoading || isSaving}
            >
              <SelectTrigger id="settings-units">
                <SelectValue placeholder={isLoading ? 'Loading…' : 'Select units'} />
              </SelectTrigger>
              <SelectContent>
                {UNITS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Save button — right-aligned */}
      <div className="flex justify-end">
        <Button
          variant="default"
          onClick={() => void handleSave()}
          disabled={isLoading || isSaving}
        >
          Save Settings
        </Button>
      </div>
    </div>
  )
}
