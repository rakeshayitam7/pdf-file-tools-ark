import './globals.css'
import './nav-icons.css'
import type { Metadata } from 'next'

export const metadata: Metadata = { title: 'File Tools ARK', description: 'Fast PDF, document, audio, video, image and data tools.' }
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html> }
