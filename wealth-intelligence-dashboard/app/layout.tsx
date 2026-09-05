import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  metadataBase: new URL('https://access-alpha.airy-spoon-9160.chatgpt.site'),
  title: 'Access Alpha | Relationship Intelligence',
  description: 'Relationship intelligence that helps private bankers turn client needs into trusted routes.',
  openGraph: {
    title: 'Access Alpha | Relationship Intelligence',
    description: 'Turn client needs into trusted routes across RM, bank and external networks.',
    images: [{ url: 'https://access-alpha.airy-spoon-9160.chatgpt.site/og.png', width: 1200, height: 630 }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Access Alpha | Relationship Intelligence',
    description: 'Turn client needs into trusted routes across RM, bank and external networks.',
    images: ['https://access-alpha.airy-spoon-9160.chatgpt.site/og.png'],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
