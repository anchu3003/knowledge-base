'use client';

import {RoleBadge} from './role-badge';
import {Button} from '@/components/ui/button';
import {Database, LogOut} from 'lucide-react';
import Link from 'next/link';

export type UserRole = "admin" | "developer"

interface AppHeaderProps {
    /** Mở drawer "Kho tài liệu" (KB-4.5). Trước đây header gọi thẳng `fetch` tới BE — đã bỏ. */
    onOpenDocuments?: () => void;
}

export function AppHeader({onOpenDocuments}: AppHeaderProps) {
    const user: { name: string, role: UserRole } | null = {
        name: 'An Chu',
        role: 'developer'
    }

    return (
        <header className="border-b border-border bg-background sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between items-center h-16">
                    {/* Logo */}
                    <Link href="/" className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                            <span className="text-primary-foreground font-bold text-lg"> O </span>
                        </div>
                        <span className="font-bold text-lg hidden sm:inline"> Knowledge Navigator </span>
                    </Link>

                    {/* Documents & health panel (KB-4.5) */}
                    <nav className="hidden md:flex items-left gap-1">
                        <Button variant="ghost" size="sm" onClick={onOpenDocuments}
                                className="gap-2" aria-label="Mở kho tài liệu">
                            <Database className="h-4 w-4"/>
                            <span className="text-sm font-medium">Kho tài liệu</span>
                        </Button>
                    </nav>

                    {/* User Info & Logout */}
                    <div className="flex items-center gap-4">
                        {user && (
                            <>
                                <div className="hidden sm:flex items-center gap-2 flex-row">
                                    <div className="text-right flex-row flex gap-2">
                                        <p className="text-sm font-medium text-foreground">{user.name}</p>
                                        <RoleBadge role={user.role} size="sm"/>
                                    </div>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => ""} className="gap-2">
                                    <LogOut className="h-4 w-4"/>
                                    <span className="hidden sm:inline">Logout</span>
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </header>
    );
}
