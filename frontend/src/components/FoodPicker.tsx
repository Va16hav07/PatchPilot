import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { grams, kcal, SOURCE_LABEL } from '../format'
import type { FoodSummary } from '../types'
import Icon from './Icon'

export function SourceTag({ source, kind }: { source: string; kind: string }) {
  return <span className={`tag${kind === 'dish' || source === 'MY_RECIPE' ? ' green' : ''}`}>{SOURCE_LABEL[source] ?? source}</span>
}

export function FoodRow({ food, onClick }: { food: FoodSummary; onClick: () => void }) {
  return (
    <button className="list-row" onClick={onClick} type="button">
      <span className="grow stack" style={{ gap: 4 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>{food.name}</span>
        <span className="row xsmall muted" style={{ gap: 6 }}>
          <SourceTag source={food.source} kind={food.kind} />
          per {food.basis}
        </span>
      </span>
      <span className="stack" style={{ gap: 2, alignItems: 'flex-end' }}>
        <span className="num" style={{ fontWeight: 700, fontSize: 14 }}>{kcal(food.energy_kcal)} kcal</span>
        <span className="xsmall muted num">{grams(food.protein_g)} g protein</span>
      </span>
    </button>
  )
}

/** Search box plus results; calls onPick with the chosen food. */
export default function FoodPicker({
  onPick,
  kind,
  initial = '',
  suggestions = [],
  autoFocus = true,
  placeholder = 'Search: dal, roti, paneer, dahi…',
}: {
  onPick: (f: FoodSummary) => void
  kind?: 'ingredient' | 'dish'
  initial?: string
  suggestions?: FoodSummary[]
  autoFocus?: boolean
  placeholder?: string
}) {
  const [q, setQ] = useState(initial)
  const [results, setResults] = useState<FoodSummary[] | null>(null)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus()
  }, [autoFocus])

  useEffect(() => {
    const term = q.trim()
    if (!term) return setResults(null)
    const t = setTimeout(() => {
      const search = new URLSearchParams({ q: term, limit: '30' })
      if (kind) search.set('kind', kind)
      api.get<FoodSummary[]>(`/api/foods?${search}`).then((r) => { setResults(r); setError('') }).catch((e) => setError(e.message))
    }, 200)
    return () => clearTimeout(t)
  }, [q, kind])

  const shown = results ?? (suggestions.length ? suggestions : null)
  return (
    <div className="stack" style={{ gap: 12 }}>
      <label className="search">
        <Icon name="search" size={20} />
        <input ref={inputRef} aria-label="Search foods" placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} />
        {q && <button type="button" className="icon-btn" aria-label="Clear" onClick={() => setQ('')} style={{ width: 36, height: 36 }}><Icon name="close" size={18} /></button>}
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      {results && results.length === 0 && <p className="small muted" style={{ margin: 0 }}>No match for "{q}". Try a simpler word or the main ingredient.</p>}
      {shown && shown.length > 0 && (
        <div className="card list" aria-live="polite">
          {shown.map((f) => <FoodRow key={f.id} food={f} onClick={() => onPick(f)} />)}
        </div>
      )}
    </div>
  )
}
