import "@testing-library/jest-dom/vitest";

// jsdom no implementa `PointerEvent` (solo `MouseEvent`/`Event`): sin esto,
// `fireEvent.pointerDown/Move/Up` de Testing Library caen a un `Event`
// genérico sin `clientX`/`clientY`/`pointerId`, y cualquier componente que
// dependa de esos campos (ej. arrastre/zoom en GraphCanvas) los recibe
// `undefined`. Polyfill mínimo: MouseEvent ya trae clientX/clientY, solo
// falta agregar `pointerId`.
// jsdom en esta config no expone `window.localStorage` (arranca sin
// `--localstorage-file`): sin esto, cualquier componente que lea/escriba
// preferencias de UI (`src/lib/uiPrefs.ts`, doc 13 §3.3) cae siempre al
// `catch` y nunca persiste, así que no se puede testear el colapso de paneles.
// Polyfill mínimo respaldado por un Map, con la misma API que `Storage`.
if (typeof globalThis.localStorage === "undefined") {
  const store = new Map<string, string>();
  const localStoragePolyfill: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => void store.delete(key),
    setItem: (key: string, value: string) => void store.set(key, String(value)),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: localStoragePolyfill,
  });
}

if (typeof globalThis.PointerEvent === "undefined") {
  class PointerEventPolyfill extends MouseEvent {
    pointerId: number;
    constructor(type: string, params: PointerEventInit = {}) {
      super(type, params);
      this.pointerId = params.pointerId ?? 0;
    }
  }
  // @ts-expect-error jsdom no expone PointerEvent — se agrega recién acá.
  globalThis.PointerEvent = PointerEventPolyfill;
}
