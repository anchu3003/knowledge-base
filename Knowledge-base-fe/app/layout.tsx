import type React from 'react';
import type {Metadata} from 'next';
import './globals.css';

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
        <html lang="en">
        <body>
        {children}
        </body>
        </html>
    );
}
