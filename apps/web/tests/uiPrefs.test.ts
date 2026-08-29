import { afterEach, describe, expect, it, vi } from "vitest";

import { collapsedByDefault, getUiPref, setUiPref } from "../src/lib/uiPrefs";

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("uiPrefs", () => {
  it("persiste y recupera un valor con el prefijo kos.ui.", () => {
    setUiPref("railCollapsed", true);
    expect(window.localStorage.getItem("kos.ui.railCollapsed")).toBe("true");
    expect(getUiPref("railCollapsed", false)).toBe(true);
  });

  it("devuelve el fallback cuando no hay nada guardado", () => {
    expect(getUiPref("noExiste", "def")).toBe("def");
  });

  it("devuelve el fallback si localStorage lanza (modo incógnito / deshabilitado)", () => {
    vi.spyOn(window.localStorage, "getItem").mockImplementation(() => {
      throw new Error("SecurityError");
    });
    expect(getUiPref("railCollapsed", "seguro")).toBe("seguro");
  });

  it("setUiPref no propaga el error si el storage está lleno", () => {
    vi.spyOn(window.localStorage, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });
    expect(() => setUiPref("railCollapsed", true)).not.toThrow();
  });

  describe("collapsedByDefault", () => {
    it("respeta la elección explícita del usuario por encima del breakpoint", () => {
      setUiPref("chatSidebarCollapsed", true);
      expect(collapsedByDefault("chatSidebarCollapsed")).toBe(true);
    });

    it("sin preferencia, colapsa cuando el viewport está por debajo de lg", () => {
      vi.stubGlobal(
        "matchMedia",
        vi.fn().mockReturnValue({ matches: false } as MediaQueryList),
      );
      expect(collapsedByDefault("chatSidebarCollapsed")).toBe(true);
    });

    it("sin preferencia, no colapsa cuando el viewport es lg o mayor", () => {
      vi.stubGlobal(
        "matchMedia",
        vi.fn().mockReturnValue({ matches: true } as MediaQueryList),
      );
      expect(collapsedByDefault("chatSidebarCollapsed")).toBe(false);
    });
  });
});
