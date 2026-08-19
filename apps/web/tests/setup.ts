import "@testing-library/jest-dom/vitest";

// jsdom no implementa `PointerEvent` (solo `MouseEvent`/`Event`): sin esto,
// `fireEvent.pointerDown/Move/Up` de Testing Library caen a un `Event`
// genérico sin `clientX`/`clientY`/`pointerId`, y cualquier componente que
// dependa de esos campos (ej. arrastre/zoom en GraphCanvas) los recibe
// `undefined`. Polyfill mínimo: MouseEvent ya trae clientX/clientY, solo
// falta agregar `pointerId`.
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
