/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        razzball: {
          primary: '#FF6B35',
          secondary: '#004E89',
          accent: '#F7B801',
        }
      }
    },
  },
  plugins: [],
}
