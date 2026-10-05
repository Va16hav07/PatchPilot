import { grams } from '../format'
import type { Nutrients, Targets } from '../types'

export const MACROS = [
  { key: 'protein_g', target: 'protein_g', label: 'Protein', color: 'var(--protein)' },
  { key: 'carb_g', target: 'carb_g', label: 'Carbs', color: 'var(--carb)' },
  { key: 'fat_g', target: 'fat_g', label: 'Fat', color: 'var(--fat)' },
  { key: 'fibre_g', target: 'fibre_g', label: 'Fibre', color: 'var(--fibre)' },
] as const

/** Progress bars against targets (Today screen). */
export function MacroBars({ totals, targets }: { totals: Nutrients; targets: Targets }) {
  return (
    <div className="grid-2">
      {MACROS.map((m) => {
        const value = totals[m.key] ?? 0
        const target = targets[m.target]
        const pct = target > 0 ? Math.min(value / target, 1) * 100 : 0
        return (
          <div key={m.key} className="stack" style={{ gap: 5 }}>
            <div className="row between small">
              <strong>{m.label}</strong>
              <span className="muted num">
                {grams(value)} / {target} g
              </span>
            </div>
            <div
              className="bar"
              role="meter"
              aria-label={m.label}
              aria-valuemin={0}
              aria-valuemax={target}
              aria-valuenow={Math.round(value)}
            >
              <div style={{ width: `${pct}%`, background: m.color }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** Four macro amounts with a colour key (portion and meal totals). */
export function MacroRow({ nutrients }: { nutrients: Nutrients }) {
  return (
    <div className="macro-grid">
      {MACROS.map((m) => (
        <div key={m.key} className="stack" style={{ gap: 4 }}>
          <div className="swatch" style={{ background: m.color }} />
          <span className="num" style={{ fontWeight: 700, fontSize: 16 }}>
            {grams(nutrients[m.key] ?? 0)} g
          </span>
          <span className="xsmall muted">{m.label}</span>
        </div>
      ))}
    </div>
  )
}
