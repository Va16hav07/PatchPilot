/** A short haptic tick for meaningful commits (a meal saved). Android browsers only; silent elsewhere. */
export function hapticCommit(): void {
  try {
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) navigator.vibrate?.(12)
  } catch {
    // unsupported: no-op
  }
}
