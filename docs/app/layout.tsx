import { Geist, JetBrains_Mono } from 'next/font/google';
import type { Metadata } from 'next';
import { Provider } from '@/components/provider';
import { appName, appTagline } from '@/lib/shared';
import './global.css';

const geist = Geist({
  subsets: ['latin'],
  variable: '--font-geist',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'https://sina-al.github.io/pymediate'),
  title: {
    default: `${appName} — ${appTagline}`,
    template: `%s | ${appName}`,
  },
  description:
    'A type-safe mediator for Python 3.12+. Route typed requests to handlers with zero dependencies, first-class async, pipeline behaviors, and full mypy support.',
};

export default function Layout({ children }: LayoutProps<'/'>) {
  return (
    <html
      lang="en"
      className={`${geist.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body className="flex flex-col min-h-screen font-sans">
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
