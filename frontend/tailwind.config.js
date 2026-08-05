/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: '#0B0E14',
          surface: '#12151F',
          raised: '#1A1E2B',
        },
        line: '#242938',
        ink: {
          DEFAULT: '#E7E9F0',
          muted: '#8890A6',
          faint: '#5A6178',
        },
        accent: {
          DEFAULT: '#F5B942',
          soft: '#F5B94222',
        },
        teal: {
          DEFAULT: '#5EEAD4',
          soft: '#5EEAD422',
        },
        status: {
          pending: '#FBBF24',
          approved: '#34D399',
          posted: '#60A5FA',
          failed: '#F87171',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.5)',
      },
      borderRadius: {
        xl2: '0.875rem',
      },
    },
  },
  plugins: [],
}
