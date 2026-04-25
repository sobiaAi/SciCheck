/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#1A1918',
        surface: '#242220',
        border: '#332F2B',
        sage: {
          DEFAULT: '#6B8C7C',
          dark: '#5C7A6B',
        },
        rose: '#C17F6B',
        amber: '#C4922A',
        blue: '#5A8FB5',
        ink: '#E8E4DF',
        muted: '#8A8480',
        cleanBg: '#1C2922',
        findingBg: '#28201D',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(0, 0, 0, 0.08)',
      },
      borderRadius: {
        lg: '8px',
      },
    },
  },
  plugins: [],
}
