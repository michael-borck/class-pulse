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
    },
  },
  plugins: [],
};
