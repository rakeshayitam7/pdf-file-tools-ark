import './globals.css'
import './nav-icons.css'
import './premium-pdf.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  metadataBase: new URL('https://pdf-file-tools-ark.vercel.app'),
  title: { default: 'File Tools ARK — Free PDF & File Tools Online', template: '%s | File Tools ARK' },
  description: 'Free online PDF, document, image, audio, video and file tools. Merge, split, compress, convert, edit and organize files with File Tools ARK.',
  applicationName: 'File Tools ARK',
  keywords: ['PDF tools','PDF converter','merge PDF','split PDF','compress PDF','PDF to Word','PDF to JPG','OCR PDF','file converter','image tools','audio tools','video tools'],
  alternates: { canonical: '/' },
  robots: { index: true, follow: true },
}
export default function RootLayout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html> }
