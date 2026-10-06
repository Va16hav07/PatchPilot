/**
 * Turn a meal description or photo into draft log items.
 *
 * Gemini never produces nutrition numbers here. It (1) splits the meal into
 * items with portions, then (2) picks each item's food from candidates our
 * database returned. Anything it picks outside those candidates is discarded.
 */
import { api } from '../api'
import type { FoodSummary, OilLevel } from '../types'
import { generateJson } from './gemini'

const UNITS = ['katori', 'bowl', 'plate', 'piece', 'roti', 'slice', 'glass', 'cup', 'can', 'bottle', 'tsp', 'tbsp', 'g', 'ml', 'serving'] as const
type AiUnit = (typeof UNITS)[number]

interface ParsedItem {
  name: string
  search_terms: string[]
  quantity: number
  unit: AiUnit
  estimated_grams: number
  oil_level: OilLevel | 'unknown'
  confidence: number
}

const PARSE_SCHEMA = {
  type: 'OBJECT',
  properties: {
    items: {
      type: 'ARRAY',
      items: {
        type: 'OBJECT',
        properties: {
          name: { type: 'STRING', description: 'Food as eaten, e.g. "Dal tadka" or "Roti"' },
          search_terms: { type: 'ARRAY', items: { type: 'STRING' }, description: '2-5 short names a food database might use, English and Indian names' },
          quantity: { type: 'NUMBER' },
          unit: { type: 'STRING', enum: [...UNITS] },
          estimated_grams: { type: 'NUMBER', description: 'Best estimate of the edible weight of the whole portion in grams' },
          oil_level: { type: 'STRING', enum: ['low', 'home', 'restaurant', 'unknown'] },
          confidence: { type: 'NUMBER', description: '0 to 1: how sure you are about the item and portion' },
        },
        required: ['name', 'search_terms', 'quantity', 'unit', 'estimated_grams', 'oil_level', 'confidence'],
      },
    },
  },
  required: ['items'],
}

const PARSE_INSTRUCTION = `You read what someone in India ate (typed, spoken in Hindi/English/Hinglish, or a photo) and list each separate food item. You never estimate calories or nutrients.

Rules:
- One entry per food actually eaten. Split combos eaten separately ("dal chawal" -> dal + rice). Keep single dishes whole ("rajma chawal" served mixed may be two items; "biryani" is one).
- Ghee or butter added on top (e.g. "ghee wali roti") is its own item: ghee, tsp, about 0.5 tsp per roti unless stated.
- Hindi numbers: ek 1, do 2, teen 3, char 4, aadha 0.5, dedh 1.5, dhai 2.5. "thoda/thodi/little" without a unit = 0.5 katori.
- unit: use what was said. Countable foods (roti, idli, dosa, egg, banana) use "piece" or "roti". Curries, dal, sabzi, rice, curd use "katori" unless said otherwise. Tea/coffee use "cup".
- estimated_grams: your best guess for the whole portion's weight (a katori of cooked dal is about 150 g, one medium roti about 40 g, one cup of tea about 150 g).
- oil_level: "restaurant" for restaurant, dhaba, hotel, takeaway, "extra ghee/butter"; "low" for "kam tel", less oil, steamed, boiled; "home" for normal home cooking; "unknown" if not clear.
- search_terms: include the English and common Indian names, and the main ingredient (e.g. "dal tadka", "toor dal", "arhar dal", "red gram dal").
- Photos: list each visible dish; estimate portions from plate, katori and spoon sizes; lower the confidence when unsure.
- Restaurant and packaged food: include the brand in name and search_terms (e.g. "Pizza Hut Margherita pizza", "KFC hot wings", "McDonald's McAloo Tikki burger", "Thums Up"). Pizza is counted in "slice"; wings, nuggets and strips in "piece"; give the size if said (personal, medium, large, regular).
- Drinks: unit "can", "bottle" or "glass"; estimated_grams = volume in ml (an Indian can is 300 ml unless said otherwise).
- Do not invent foods that were not mentioned or visible.`

const CHOOSE_SCHEMA = {
  type: 'OBJECT',
  properties: {
    choices: {
      type: 'ARRAY',
      items: {
        type: 'OBJECT',
        properties: {
          item: { type: 'INTEGER' },
          food_id: { type: 'STRING', nullable: true },
          confidence: { type: 'NUMBER' },
        },
        required: ['item', 'food_id', 'confidence'],
      },
    },
  },
  required: ['choices'],
}

const CHOOSE_INSTRUCTION = `Match each eaten item to the single best food from ITS OWN candidate list, using the exact id. Return null if no candidate is a reasonable match; never use an id that is not in that item's list.
- Prefer a cooked dish when a prepared dish was eaten (dal -> a cooked dal dish, not raw dal grains; rice -> boiled rice).
- Prefer a raw ingredient for foods eaten as they are (fruit, milk, curd, salad vegetables, ghee, sugar).
- For branded food (Pizza Hut, KFC, McDonald's, drinks), pick the same brand, product and size when listed; if the brand isn't listed, return null rather than another brand.
- "MY_RECIPE" candidates are the person's own recipes: prefer them when the name fits.
- confidence 0 to 1.`

export interface Draft {
  key: string
  phrase: string
  food: FoodSummary | null
  candidates: FoodSummary[]
  quantity: number
  unit: string
  oil_level: OilLevel
  confidence: number
  /** Why this item needs a look before saving, if it does. */
  check: string | null
}

export type MealInput = { text: string } | { image: { mimeType: string; data: string }; note?: string }

const CONTAINER_UNITS = new Set(['katori', 'bowl'])
const VOLUME_UNITS = new Set(['tsp', 'tbsp', 'katori', 'cup', 'glass', 'ml'])

/** Translate the AI's portion into a unit this food supports. */
export function mapPortion(item: { quantity: number; unit: string; estimated_grams: number }, food: FoodSummary): { quantity: number; unit: string; check: string | null } {
  const q = item.quantity > 0 ? item.quantity : 1
  const u = item.unit
  if (food.kind === 'dish') {
    if (CONTAINER_UNITS.has(u) && food.units.includes('katori')) return { quantity: q, unit: 'katori', check: null }
    if (u === 'g' || u === 'ml') return { quantity: 1, unit: 'serving', check: 'Portion was given by weight; check the number of servings' }
    return { quantity: q, unit: 'serving', check: null }
  }
  if (u === 'g') return { quantity: q, unit: 'g', check: null }
  const asUnit = u === 'bowl' ? 'katori' : u
  if (VOLUME_UNITS.has(asUnit) && food.units.includes(asUnit)) return { quantity: q, unit: asUnit, check: null }
  if (item.estimated_grams > 0) return { quantity: Math.round(item.estimated_grams), unit: 'g', check: 'Weight estimated by AI; adjust if you know it' }
  return { quantity: 100, unit: 'g', check: 'Set the amount' }
}

let seq = 0

export async function analyseMeal(input: MealInput): Promise<Draft[]> {
  const parts =
    'text' in input
      ? [{ text: `Meal: ${input.text}` }]
      : [{ inlineData: input.image }, { text: input.note ? `Photo of a meal. Note from the person: ${input.note}` : 'Photo of a meal.' }]

  const parsed = await generateJson<{ items: ParsedItem[] }>(
    { systemInstruction: { parts: [{ text: PARSE_INSTRUCTION }] }, contents: [{ role: 'user', parts }] },
    PARSE_SCHEMA,
  )
  const items = (parsed.items ?? []).filter((i) => i.name?.trim()).slice(0, 20)
  if (items.length === 0) return []

  const candidates = await api.post<FoodSummary[][]>('/api/foods/candidates', {
    items: items.map((i) => ({ terms: [i.name, ...(i.search_terms ?? [])].map((t) => t.trim()).filter(Boolean).slice(0, 6) })),
  })

  const listing = items
    .map((it, idx) => {
      const opts = candidates[idx].map((f) => `  - ${f.id}: ${f.name} [${f.source}, per ${f.basis}]${f.local_names.length ? ` (${f.local_names.slice(0, 4).join(', ')})` : ''}`)
      return `Item ${idx}: "${it.name}" (${it.quantity} ${it.unit})\n${opts.length ? opts.join('\n') : '  (no candidates)'}`
    })
    .join('\n\n')

  const anyCandidates = candidates.some((c) => c.length > 0)
  const chosen = anyCandidates
    ? await generateJson<{ choices: { item: number; food_id: string | null; confidence: number }[] }>(
        { systemInstruction: { parts: [{ text: CHOOSE_INSTRUCTION }] }, contents: [{ role: 'user', parts: [{ text: listing }] }] },
        CHOOSE_SCHEMA,
      )
    : { choices: [] }

  return items.map((it, idx) => {
    const options = candidates[idx]
    const choice = chosen.choices?.find((c) => c.item === idx)
    const food = options.find((f) => f.id === choice?.food_id) ?? null // only ids we offered
    const confidence = Math.min(it.confidence ?? 0, choice?.confidence ?? 0)
    const oil: OilLevel = it.oil_level === 'low' || it.oil_level === 'restaurant' ? it.oil_level : 'home'
    let check: string | null = null
    let portion = { quantity: it.quantity, unit: it.unit as string }
    if (!food) {
      check = options.length ? 'Pick the right food' : 'Not found in the food database; search for it or remove it'
    } else {
      const mapped = mapPortion(it, food)
      portion = mapped
      check = mapped.check ?? (confidence < 0.6 ? 'Not sure about this one; please check' : null)
    }
    return { key: `d${++seq}`, phrase: it.name, food, candidates: options, ...portion, oil_level: oil, confidence, check }
  })
}

/** Shrink a photo before sending it to Gemini. */
export async function compressImage(file: File, maxSide = 1280): Promise<{ mimeType: string; data: string }> {
  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(bitmap.width * scale)
  canvas.height = Math.round(bitmap.height * scale)
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Could not read the photo'))), 'image/jpeg', 0.85))
  const buffer = new Uint8Array(await blob.arrayBuffer())
  let binary = ''
  for (let i = 0; i < buffer.length; i += 0x8000) binary += String.fromCharCode(...buffer.subarray(i, i + 0x8000))
  return { mimeType: 'image/jpeg', data: btoa(binary) }
}
