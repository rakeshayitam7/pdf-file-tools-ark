import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = { title: 'PDF & File Tools ARK', description: 'Fast, private PDF and file conversion tools.' }
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>
}
