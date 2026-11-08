import type React from 'react';
import type {Metadata} from 'next';
import './globals.css';
import {AppProviders} from '@/components/app-providers';
import {THEME_INIT_SCRIPT} from '@/lib/theme';

export const metadata: Metadata = {
    title: 'Personal Knowledge Base',
    description: 'Intelligent document processing and AI-powered knowledge base for personal use.',
    generator: 'v0.app',
};

export default function RootLayout({
                                       children,
                                   }: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        // `suppressHydrationWarning`: class `.dark` do script inline set trước hydrate (KB-4.8)
        <html lang="vi" suppressHydrationWarning>
        <head>
            {/* Chống FOUC: áp theme TRƯỚC khi React hydrate (KB-4.8) */}
            <script dangerouslySetInnerHTML={{__html: THEME_INIT_SCRIPT}}/>
        </head>
        <body className="min-h-svh bg-background text-foreground antialiased">
        <AppProviders>{children}</AppProviders>
        </body>
        </html>
    );
}
