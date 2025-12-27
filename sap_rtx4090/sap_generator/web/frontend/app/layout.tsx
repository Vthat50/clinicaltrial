import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SAP Generator',
  description: 'Generate Statistical Analysis Plans from clinical trial protocols',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <nav className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16 items-center">
              <div className="flex items-center">
                <span className="text-xl font-bold text-indigo-600">SAP Generator</span>
                <span className="ml-2 text-sm text-gray-500">Clinical Trial SAP Automation</span>
              </div>
              <div className="flex items-center space-x-4">
                <a href="/" className="text-gray-600 hover:text-gray-900">Generate</a>
                <a href="/history" className="text-gray-600 hover:text-gray-900">History</a>
              </div>
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          {children}
        </main>
      </body>
    </html>
  )
}
