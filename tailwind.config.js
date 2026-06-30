/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./templates/**/*.html'],
  safelist: [
    // Utility classes that are only ever applied at runtime from JS strings,
    // so Tailwind can't discover them by scanning the templates statically.
    'text-blue-600',
    'text-green-600',
    'text-red-600',
    'text-gray-400',
    'bg-gray-400',
    'bg-green-50',
    'border-green-200',
    'bg-red-50',
    'border-red-200',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      // The single source of truth for the ClassPulse brand palette.
      // indigo / violet / pink come from Tailwind's defaults and already match
      // the landing page (indigo-600 #4f46e5, violet-500 #8b5cf6, pink-500 #ec4899).
      colors: {
        navy: {
          DEFAULT: '#0b0f24', // landing hero background
          800: '#11152f',
          700: '#1b2138',
        },
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #4f46e5, #8b5cf6)',
        'brand-gradient-soft': 'linear-gradient(135deg, rgba(79,70,229,0.12), rgba(139,92,246,0.12))',
        'brand-hero': 'radial-gradient(55% 60% at 78% -5%, rgba(99,102,241,0.45), transparent 70%), radial-gradient(45% 50% at 8% 15%, rgba(236,72,153,0.30), transparent 70%), radial-gradient(40% 40% at 60% 110%, rgba(139,92,246,0.30), transparent 70%)',
      },
      boxShadow: {
        'brand': '0 8px 20px -8px rgba(79,70,229,0.7)',
        'card': '0 18px 40px -24px rgba(15,18,38,0.35)',
      },
      keyframes: {
        pulseDot: {
          '0%': { boxShadow: '0 0 0 0 rgba(236,72,153,0.55)' },
          '70%': { boxShadow: '0 0 0 10px rgba(236,72,153,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(236,72,153,0)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.25' },
        },
      },
      animation: {
        'pulse-dot': 'pulseDot 2s infinite',
        'blink': 'blink 1.4s infinite',
      },
    },
  },
  plugins: [],
};
