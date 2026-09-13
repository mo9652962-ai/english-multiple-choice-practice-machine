import { post } from '../api'

const CONSENT_KEY = 'epm_local_metrics_consent'

export function localMetricsEnabled(): boolean {
  return localStorage.getItem(CONSENT_KEY) === 'enabled'
}

export function setLocalMetricsEnabled(enabled: boolean): void {
  if (enabled) localStorage.setItem(CONSENT_KEY, 'enabled')
  else localStorage.removeItem(CONSENT_KEY)
}

export async function trackMetric(
  eventName: string,
  detail: Record<string, string | number> = {},
): Promise<void> {
  if (!localMetricsEnabled()) return
  try {
    await post('/metrics/events', { event_name: eventName, detail })
  } catch {
    // Metrics are best-effort and must never interrupt learning.
  }
}
