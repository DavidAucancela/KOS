// Preferencias de presentación del usuario en `localStorage` (doc 13 §3.3):
// primer uso de `localStorage` en apps/web, acotado a cómo se ve la interfaz —
// nunca datos de dominio (esos vienen siempre de la API, regla doc 01). Sin
// estado ni React acá: solo lectura/escritura tolerante a fallos, para que
// respete la regla "lib/ = utilidades sin estado" de doc 10 §4.
//
// Tolerante a modo incógnito / storage deshabilitado / cuota llena: si algo
// falla, `get` devuelve el fallback y `set` no rompe — una preferencia que no
// persiste no es un error fatal.

const PREFIX = "kos.ui.";

export function getUiPref<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(PREFIX + key);
    if (raw === null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function setUiPref<T>(key: string, value: T): void {
  try {
    window.localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // storage deshabilitado o lleno — la preferencia no persiste, se ignora.
  }
}

// Default responsivo para un panel colapsable (doc 13 §3.5): si el usuario ya
// eligió explícitamente, gana su elección; si no, colapsado bajo el breakpoint
// `lg` (1024px). `matchMedia` no existe en algunos entornos de test (jsdom) —
// ahí se asume expandido.
export function collapsedByDefault(key: string): boolean {
  const stored = getUiPref<boolean | null>(key, null);
  if (stored !== null) return stored;
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    return !window.matchMedia("(min-width: 1024px)").matches;
  }
  return false;
}
