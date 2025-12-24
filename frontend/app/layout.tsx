import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Fantasy Baseball Chatbot - Powered by Razzball',
  description: 'AI-powered fantasy baseball assistant',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50">{children}</body>
    </html>
  )
}
