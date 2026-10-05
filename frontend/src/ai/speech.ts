/** Browser speech-to-text (Web Speech API). Chrome, Edge and Safari support it. */

interface SpeechRecognitionResultLike {
  isFinal: boolean
  0: { transcript: string }
}
interface SpeechRecognitionEventLike {
  resultIndex: number
  results: ArrayLike<SpeechRecognitionResultLike>
}
interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: SpeechRecognitionEventLike) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start(): void
  stop(): void
}

type Ctor = new () => SpeechRecognitionLike

function ctor(): Ctor | null {
  const w = window as unknown as { SpeechRecognition?: Ctor; webkitSpeechRecognition?: Ctor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export const speechSupported = () => ctor() !== null

export interface Listening {
  stop(): void
}

/** Start listening; `onText` gets the full transcript so far (final + interim). */
export function listen(
  lang: 'en-IN' | 'hi-IN',
  onText: (text: string) => void,
  onEnd: (error: string | null) => void,
): Listening {
  const Recognition = ctor()
  if (!Recognition) {
    onEnd('Voice input is not supported in this browser. Try Chrome.')
    return { stop() {} }
  }
  const rec = new Recognition()
  rec.lang = lang
  rec.continuous = true
  rec.interimResults = true
  let finalText = ''
  let error: string | null = null
  rec.onresult = (e) => {
    let interim = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i]
      if (r.isFinal) finalText += r[0].transcript + ' '
      else interim += r[0].transcript
    }
    onText((finalText + interim).trim())
  }
  rec.onerror = (e) => {
    error = e.error === 'not-allowed' ? 'Microphone permission was denied.' : e.error === 'no-speech' ? null : `Voice input error: ${e.error}`
  }
  rec.onend = () => onEnd(error)
  rec.start()
  return { stop: () => rec.stop() }
}
