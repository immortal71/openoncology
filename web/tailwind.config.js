/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}'
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        mono: ['var(--font-mono)', 'JetBrains Mono', 'ui-monospace', 'monospace'],
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
      },
    },
  },
  plugins: [],
};
