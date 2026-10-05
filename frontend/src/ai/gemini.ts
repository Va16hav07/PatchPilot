/**
 * Gemini access.
 *
 * The user's own key lives only in this browser (localStorage) and is sent
 * only to Google, never to our server. Without one, requests go through our
 * server's shared key (/api/ai/generate), if the server has one.
 */
import { api, ApiError } from '../api'

const KEY_STORAGE = 'thali.geminiKey'
const GEMINI = 'https://generativelanguage.googleapis.com/v1beta'
export const MODELS = ['gemini-3.6-flash', 'gemini-3.8-flash', 'gemini-3.5-flash-lite']

export class AiError extends Error {}

export function getDeviceKey(): string | null {
  try {
    return localStorage.getItem(KEY_STORAGE)
  } catch {
    return null
  }
}

export function setDeviceKey(key: string | null): void {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key.trim())
    else localStorage.removeItem(KEY_STORAGE)
  } catch {
    throw new AiError('This browser is blocking storage, so the key cannot be saved on this device.')
  }
}

/** Checks a key directly with Google. Returns an error message, or null if it works. */
export async function testKey(key: string): Promise<string | null> {
  try {
    const res = await fetch(`${GEMINI}/models?pageSize=100`, { headers: { 'x-goog-api-key': key.trim() } })
    if (res.ok) return null
    if (res.status === 400 || res.status === 401 || res.status === 403) return 'Google rejected this key. Check it was copied fully from AI Studio.'
    return `Google returned an error (${res.status}). Try again in a minute.`
  } catch {
    return 'Could not reach Google. Check your internet connection.'
  }
}

export interface AiStatus {
  server_key: boolean
  models: string[]
  daily_limit: number
}

let statusCache: Promise<AiStatus> | null = null
export function aiStatus(): Promise<AiStatus> {
  statusCache ??= api.get<AiStatus>('/api/ai/status').catch(() => ({ server_key: false, models: [], daily_limit: 0 }))
  return statusCache
}

export async function aiAvailable(): Promise<boolean> {
  return Boolean(getDeviceKey()) || (await aiStatus()).server_key
}

export interface GenerateRequest {
  contents: unknown[]
  generationConfig?: Record<string, unknown>
  systemInstruction?: Record<string, unknown>
}

interface GeminiResponse {
  candidates?: { content?: { parts?: { text?: string }[] }; finishReason?: string }[]
  promptFeedback?: { blockReason?: string }
}

/** This model can't serve the request right now (missing, overloaded): try the next one. */
class ModelUnavailable extends Error {}

const TRANSIENT = new Set([500, 502, 503, 504])
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function googleMessage(res: Response): Promise<string> {
  const body = await res.text()
  try {
    return (JSON.parse(body)?.error?.message as string) || body.slice(0, 300)
  } catch {
    return body.slice(0, 300)
  }
}

async function direct(key: string, model: string, req: GenerateRequest): Promise<GeminiResponse> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const res = await fetch(`${GEMINI}/models/${model}:generateContent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key },
      body: JSON.stringify(req),
    })
    if (res.ok) return res.json()
    if (TRANSIENT.has(res.status)) {
      console.warn(`[gemini] ${model} returned ${res.status}${attempt === 0 ? ', retrying' : ', trying next model'}`)
      if (attempt === 0) await sleep(1200)
      continue
    }
    if (res.status === 404) throw new ModelUnavailable(model)
    const message = await googleMessage(res)
    console.error(`[gemini] ${model} ${res.status}: ${message}`)
    if (res.status === 429) throw new AiError('Your Gemini key is over its quota. Try again later.')
    if (/api key|API_KEY_INVALID|permission/i.test(message)) throw new AiError('Your Gemini key was rejected. Update it in Profile.')
    throw new AiError(`Gemini rejected the request (${res.status}): ${message}`)
  }
  throw new ModelUnavailable(model)
}

async function viaServer(model: string, req: GenerateRequest): Promise<GeminiResponse> {
  try {
    return await api.post<GeminiResponse>('/api/ai/generate', { model, ...req })
  } catch (e) {
    // The relay reports Google's status as "Gemini returned an error (NNN)".
    if (e instanceof ApiError && e.status === 502 && /\((404|50\d)\)/.test(e.message)) throw new ModelUnavailable(model)
    throw new AiError(e instanceof Error ? e.message : 'AI request failed')
  }
}

/** Run a request, trying the device key first, then the server key; each across MODELS in order. */
async function run(req: GenerateRequest): Promise<GeminiResponse> {
  const key = getDeviceKey()
  const status = await aiStatus()
  const routes: ((m: string) => Promise<GeminiResponse>)[] = []
  if (key) routes.push((m) => direct(key, m, req))
  if (status.server_key) routes.push((m) => viaServer(m, req))
  if (routes.length === 0) throw new AiError('AI logging needs a Gemini key. Add yours in Profile (it stays on this device).')

  let lastError: unknown = null
  for (const route of routes) {
    for (const model of MODELS) {
      try {
        return await route(model)
      } catch (e) {
        lastError = e
        if (e instanceof ModelUnavailable) continue // try the next model
        break // this route failed for another reason: try the next route
      }
    }
  }
  if (lastError instanceof AiError) throw lastError
  throw new AiError('Gemini is busy right now (all models unavailable). Please try again in a minute.')
}

/** Generate and parse JSON that matches `schema`. */
export async function generateJson<T>(req: GenerateRequest, schema: Record<string, unknown>): Promise<T> {
  const res = await run({
    ...req,
    generationConfig: { ...req.generationConfig, responseMimeType: 'application/json', responseSchema: schema, temperature: 0 },
  })
  if (res.promptFeedback?.blockReason) throw new AiError('Gemini declined this request.')
  const text = res.candidates?.[0]?.content?.parts?.map((p) => p.text ?? '').join('') ?? ''
  try {
    return JSON.parse(text) as T
  } catch {
    throw new AiError('Gemini returned an unreadable answer. Try again.')
  }
}
