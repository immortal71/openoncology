"use client";

import { createContext, useContext, useState, useSyncExternalStore } from "react";

type HighlightStore = {
  get: () => string | null;
  setHover: (id: string | null) => void;
  setFocus: (id: string | null) => void;
  subscribe: (listener: () => void) => () => void;
};

function createHighlightStore(): HighlightStore {
  let hover: string | null = null;
  let focus: string | null = null;
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach((l) => l());
  return {
    get: () => hover ?? focus,
    setHover: (id) => {
      hover = id;
      emit();
    },
    setFocus: (id) => {
      focus = id;
      emit();
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

const HighlightContext = createContext<HighlightStore | null>(null);
const noopSubscribe = () => () => {};

export function HighlightProvider({ children }: { children: React.ReactNode }) {
  const [store] = useState(createHighlightStore);
  return <HighlightContext.Provider value={store}>{children}</HighlightContext.Provider>;
}

export function useHighlightStore() {
  return useContext(HighlightContext);
}

export function useIsHighlighted(id: string) {
  const store = useContext(HighlightContext);
  return useSyncExternalStore(
    store ? store.subscribe : noopSubscribe,
    () => (store ? store.get() === id : false),
    () => false
  );
}

export function highlightHandlers(store: HighlightStore | null, id: string) {
  return {
    onPointerEnter: (e: React.PointerEvent) => {
      if (e.pointerType === "mouse") store?.setHover(id);
    },
    onPointerLeave: (e: React.PointerEvent) => {
      if (e.pointerType === "mouse") store?.setHover(null);
    },
  };
}
