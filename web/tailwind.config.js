/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}'
  ],
  darkMode: 'class',
  future: {
    hoverOnlyWhenSupported: true,
  },
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-plex)', 'IBM Plex Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'IBM Plex Mono', 'ui-monospace', 'monospace'],
        display: ['var(--font-display)', 'Georgia', 'serif'],
      },
      colors: {
        'accent-warm': 'hsl(var(--accent-warm))',
        'accent-warm-deep': 'hsl(var(--accent-warm-deep))',
        neutral: {
          bg: 'var(--neutral-bg)',
          muted: 'var(--neutral-muted)',
          body: 'var(--neutral-body)',
          heading: 'var(--neutral-heading)',
        },
        oo: {
          paper: 'rgb(var(--oo-paper) / <alpha-value>)',
          surface: 'rgb(var(--oo-surface) / <alpha-value>)',
          line: 'rgb(var(--oo-line) / <alpha-value>)',
          'line-soft': 'rgb(var(--oo-line-soft) / <alpha-value>)',
          ink: 'rgb(var(--oo-ink) / <alpha-value>)',
          'ink-2': 'rgb(var(--oo-ink-2) / <alpha-value>)',
          'ink-3': 'rgb(var(--oo-ink-3) / <alpha-value>)',
          muted: 'rgb(var(--oo-muted) / <alpha-value>)',
          hema: 'rgb(var(--oo-hema) / <alpha-value>)',
          'hema-hover': 'rgb(var(--oo-hema-hover) / <alpha-value>)',
          'hema-tint': 'rgb(var(--oo-hema-tint) / <alpha-value>)',
          'hema-on-dark': 'rgb(var(--oo-hema-on-dark) / <alpha-value>)',
          eosin: 'rgb(var(--oo-eosin) / <alpha-value>)',
          'eosin-tint': 'rgb(var(--oo-eosin-tint) / <alpha-value>)',
          status: {
            'queued-bg': 'rgb(var(--oo-queued-bg) / <alpha-value>)',
            'queued-fg': 'rgb(var(--oo-queued-fg) / <alpha-value>)',
            'analyzing-bg': 'rgb(var(--oo-analyzing-bg) / <alpha-value>)',
            'analyzing-fg': 'rgb(var(--oo-analyzing-fg) / <alpha-value>)',
            'complete-bg': 'rgb(var(--oo-complete-bg) / <alpha-value>)',
            'complete-fg': 'rgb(var(--oo-complete-fg) / <alpha-value>)',
            'failed-bg': 'rgb(var(--oo-failed-bg) / <alpha-value>)',
            'failed-fg': 'rgb(var(--oo-failed-fg) / <alpha-value>)',
            'failed-hover': 'rgb(var(--oo-failed-hover) / <alpha-value>)',
          },
        },
      },
      transitionTimingFunction: {
        'oo-out': 'cubic-bezier(0.22, 1, 0.36, 1)',
        'oo-in-out': 'cubic-bezier(0.65, 0, 0.35, 1)',
      },
    },
  },
  plugins: [],
};
