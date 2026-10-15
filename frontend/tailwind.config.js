/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        eggplant: '#2d2438',
        'eggplant-glass': 'rgba(45, 36, 56, 0.90)',
        lavender: '#f5f1fa',
        wisteria: '#8b6b9e',
        'wisteria-ghost': '#f3eef8',
        plum: '#5a3e6b',
        mauve: '#c49dbd',
        lilac: '#b8a9c6',
        'lilac-light': '#d4cce0',
        blue: {
          DEFAULT: '#6b9ccc',
          dark: '#5a8ab5',
        },
      },
      fontFamily: {
        brand: ['"STSong"', '"Songti SC"', 'serif'],
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Noto Sans SC"', 'sans-serif'],
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '16px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(45,36,56,0.06)',
        elevated: '0 4px 16px rgba(45,36,56,0.08)',
      },
      transitionDuration: {
        DEFAULT: '180ms',
      },
      animation: {
        'msg-in': 'msgIn 0.3s ease-out',
        'report-in': 'reportIn 0.4s ease-out',
        'spin-slow': 'spin 0.6s linear infinite',
        'dots': 'dots 1.4s steps(4, end) infinite',
      },
      keyframes: {
        msgIn: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        reportIn: {
          from: { opacity: '0', transform: 'translateX(20px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        dots: {
          '0%': { content: '""' },
          '25%': { content: '"."' },
          '50%': { content: '".."' },
          '75%': { content: '"..."' },
          '100%': { content: '""' },
        },
      },
    },
  },
  plugins: [],
}
