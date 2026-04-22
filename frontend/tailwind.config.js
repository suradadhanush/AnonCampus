/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-syne)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains)', 'monospace'],
        display: ['var(--font-syne)', 'sans-serif'],
      },
      colors: {
        carbon: {
          950: '#080A0F',
          900: '#0D1117',
          800: '#141922',
          700: '#1C2333',
          600: '#242D40',
          500: '#2D3854',
        },
        signal: {
          green: '#00FF88',
          cyan: '#00D4FF',
          amber: '#FFB800',
          red: '#FF4444',
          purple: '#B44FFF',
        },
        slate: {
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
        }
      },
      backgroundImage: {
        'grid-pattern': "linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)",
        'glow-green': 'radial-gradient(ellipse 60% 40% at 50% 0%, rgba(0,255,136,0.12) 0%, transparent 70%)',
        'glow-cyan': 'radial-gradient(ellipse 60% 40% at 50% 0%, rgba(0,212,255,0.10) 0%, transparent 70%)',
      },
      backgroundSize: {
        'grid': '40px 40px',
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'slide-up': 'slideUp 0.4s ease-out',
        'fade-in': 'fadeIn 0.3s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
        'scan': 'scan 2s ease-in-out infinite',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(16px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        scan: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '1' },
        },
      },
      boxShadow: {
        'glow-green': '0 0 20px rgba(0,255,136,0.2)',
        'glow-cyan': '0 0 20px rgba(0,212,255,0.2)',
        'glow-amber': '0 0 20px rgba(255,184,0,0.2)',
        'card': '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)',
        'card-hover': '0 4px 20px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,212,255,0.15)',
      },
    },
  },
  plugins: [],
}
