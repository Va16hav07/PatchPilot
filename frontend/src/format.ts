/** Local calendar date as YYYY-MM-DD. */
export function isoDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function parseIsoDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(s: string, n: number): string {
  const d = parseIsoDate(s)
  d.setDate(d.getDate() + n)
  return isoDate(d)
}

export function today(): string {
  return isoDate(new Date())
}

export function dayLabel(s: string): string {
  if (s === today()) return 'Today'
  if (s === addDays(today(), -1)) return 'Yesterday'
  return parseIsoDate(s).toLocaleDateString('en-IN', { weekday: 'long' })
}

export function longDate(s: string): string {
  return parseIsoDate(s).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
}

export const kcal = (n: number) => Math.round(n).toLocaleString('en-IN')

/** 1 decimal under 10, whole numbers above. */
export function grams(n: number): string {
  return n < 10 ? (Math.round(n * 10) / 10).toString() : Math.round(n).toString()
}

export function qty(n: number): string {
  return (Math.round(n * 100) / 100).toString()
}

const UNIT_LABEL: Record<string, string> = {
  g: 'g',
  ml: 'ml',
  tsp: 'tsp',
  tbsp: 'tbsp',
  katori: 'katori',
  cup: 'cup',
  glass: 'glass',
}

export function unitLabel(unit: string, servingUnit?: string | null): string {
  if (unit === 'serving') return servingUnit ?? 'serving'
  return UNIT_LABEL[unit] ?? unit
}

export const SOURCE_LABEL: Record<string, string> = {
  IFCT2017: 'IFCT 2017',
  INDB: 'INDB recipe',
  USDA: 'USDA',
  MY_RECIPE: 'My recipe',
}
