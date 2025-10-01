/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      screens: {
        'xs': '480px',
        'sm': '640px',
        'md': '768px',
        'lg': '1024px',
        'xl': '1280px',
        '2xl': '1600px',
        '3xl': '1920px',
      },
      spacing: {
        'responsive-xs': 'var(--spacing-xs)',
        'responsive-sm': 'var(--spacing-sm)',
        'responsive-md': 'var(--spacing-md)',
        'responsive-lg': 'var(--spacing-lg)',
        'responsive-xl': 'var(--spacing-xl)',
        'responsive-2xl': 'var(--spacing-2xl)',
      },
      fontSize: {
        'responsive-xs': 'var(--text-xs)',
        'responsive-sm': 'var(--text-sm)',
        'responsive-base': 'var(--text-base)',
        'responsive-lg': 'var(--text-lg)',
        'responsive-xl': 'var(--text-xl)',
        'responsive-2xl': 'var(--text-2xl)',
        'responsive-3xl': 'var(--text-3xl)',
        'responsive-4xl': 'var(--text-4xl)',
      },
      width: {
        'presentation': 'var(--presentation-image-width)',
        'grid-image': 'var(--grid-image-size)',
        'modal': 'var(--modal-width)',
      },
      height: {
        'presentation': 'var(--presentation-image-height)',
        'grid-image': 'var(--grid-image-height)',
        'modal': 'var(--modal-height)',
      },
      gap: {
        'presentation': 'var(--presentation-gap)',
      },
      aspectRatio: {
        'presentation': 'var(--aspect-presentation)',
        'photo': 'var(--aspect-photo)',
      },
    },
  },
  plugins: [],
};
