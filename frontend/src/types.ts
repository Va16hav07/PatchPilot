export type Nutrients = Record<string, number>

export type Sex = 'male' | 'female'
export type Activity = 'sedentary' | 'moderate' | 'heavy'
export type Goal = 'lose' | 'maintain' | 'gain'
export type Meal = 'breakfast' | 'lunch' | 'snacks' | 'dinner'
export type OilLevel = 'low' | 'home' | 'restaurant'
export type Diet = 'vegetarian' | 'eggetarian' | 'non_vegetarian' | 'jain'

export const DIETS: [Diet, string][] = [
  ['vegetarian', 'Vegetarian'],
  ['eggetarian', 'Eggetarian'],
  ['non_vegetarian', 'Non-veg'],
  ['jain', 'Jain'],
]

export const MEALS: { key: Meal; label: string }[] = [
  { key: 'breakfast', label: 'Breakfast' },
  { key: 'lunch', label: 'Lunch' },
  { key: 'snacks', label: 'Snacks' },
  { key: 'dinner', label: 'Dinner' },
]

export interface Profile {
  sex: Sex
  age: number
  height_cm: number
  weight_kg: number
  activity: Activity
  goal: Goal
  diet: Diet | null
}

export interface Targets {
  energy_kcal: number
  protein_g: number
  carb_g: number
  fat_g: number
  fibre_g: number
}

export interface Measures {
  katori_ml: number
  glass_ml: number
}

export interface User {
  id: string
  email: string
  name: string
  picture: string | null
  profile: Profile | null
  targets: Targets | null
  targets_custom: boolean
  measures: Measures
}

export interface FoodSummary {
  id: string
  name: string
  source: string
  kind: 'ingredient' | 'dish'
  local_names: string[]
  basis: string
  energy_kcal: number
  protein_g: number
  units: string[]
}

export interface FoodDetail extends FoodSummary {
  nutrients: Nutrients
  group: string | null
  serving_unit: string | null
  added_fat_g: number | null
  ingredients: { name: string; code: string; amount: number; unit: string }[] | null
  derived_from: string | null
  quality_flags: string[]
}

export interface PortionResult {
  nutrients: Nutrients
  grams: number | null
  servings: number | null
  assumptions: string[]
}

export interface LogEntry extends PortionResult {
  id: string
  date: string
  meal: Meal
  food_id: string
  food_name: string
  source: string
  quantity: number
  unit: string
  serving_unit: string | null
  oil_level: OilLevel
}

export interface Day {
  date: string
  targets: Targets | null
  totals: Nutrients
  meals: Record<Meal, LogEntry[]>
}

export interface DaySummary {
  date: string
  totals: Nutrients
  entries: number
}

export interface NutrientAvg {
  key: string
  label: string
  unit: string
  avg: number
  target: number
  pct: number
}

export interface MicroAvg extends NutrientAvg {
  ear: number | null
  status: 'good' | 'borderline' | 'low'
}

export interface LimitAvg {
  key: string
  label: string
  unit: string
  avg: number
  limit: number
  over: boolean
}

export interface SuggestedFood {
  id: string
  name: string
  source: string
  portion: string
  amount: number
  pct_of_target: number
  energy_kcal: number
  you_eat_it: boolean
}

export interface Suggestion {
  key: string
  label: string
  unit: string
  gap: number
  foods: SuggestedFood[]
}

export interface Insights {
  start: string
  end: string
  days_logged: number
  enough_data: boolean
  diet: Diet | null
  energy: NutrientAvg | null
  macros: NutrientAvg[]
  micros: MicroAvg[]
  limits: LimitAvg[]
  suggestions: Suggestion[]
}
