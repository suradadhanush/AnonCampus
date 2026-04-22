import type { Metadata } from 'next'
import './globals.css'
import { Providers } from '@/components/layout/Providers'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Toaster } from 'react-hot-toast'

export const metadata: Metadata = {
  title: 'AnonCampus — Grievance Intelligence Platform',
  description: 'Anonymous, structured, evidence-driven student grievance signals for institutions.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-carbon-950 text-white antialiased">
        <ErrorBoundary>
          <Providers>
            {children}
            <Toaster
              position="bottom-right"
              toastOptions={{
                style: {
                  background: '#141922',
                  color: '#E2E8F0',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '10px',
                  fontFamily: 'Syne, sans-serif',
                  fontSize: '14px',
                },
                success: { iconTheme: { primary: '#00FF88', secondary: '#080A0F' } },
                error: { iconTheme: { primary: '#FF4444', secondary: '#080A0F' } },
              }}
            />
          </Providers>
        </ErrorBoundary>
      </body>
    </html>
  )
}
