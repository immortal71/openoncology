export const EASE_OUT = [0.22, 1, 0.36, 1] as const;
export const EASE_IN_OUT = [0.65, 0, 0.35, 1] as const;

export const DURATION = {
  micro: 0.15,
  base: 0.25,
  slow: 0.4,
  countUp: 0.8,
} as const;

export const SPRING_UI = { type: "spring", stiffness: 400, damping: 34 } as const;
export const SPRING_PANEL = { type: "spring", stiffness: 260, damping: 30 } as const;

export const EXPAND = { duration: DURATION.base, ease: EASE_OUT } as const;
