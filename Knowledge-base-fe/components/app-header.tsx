'use client';

import {RoleBadge} from './role-badge';
import {Button} from '@/components/ui/button';
import {LogOut} from 'lucide-react';
import Link from 'next/link';

export type UserRole = "admin" | "developer"


export function AppHeader() {
    const user: { name: string, role: UserRole } | null = {
        name: 'An Chu',
        role: 'developer'
    }

    const getNavItems = () => {
        if (!user) return [];

        const baseItems = [
            {label: 'Refresh', href: 'http://localhost:8000/documents/refresh'},
            {label: 'Clear', href: 'http://localhost:8000/documents/clear'},
        ];
        // if (user.role === 'admin') {
        //     return [
        //         ...baseItems,
        //         {label: 'Settings', href: '/settings'},
        //     ];
        // }
        return [...baseItems];
    };

    const handleClickMenu = async (
        label: string
    ) => {
        let link = "";
        let method = "GET";
        switch (label) {
            case 'Refresh':
                link = "http://localhost:8000/documents/refresh";
                method = "POST";
                break;
            case 'Clear':
                link = "http://localhost:8000/documents/clear";
                method = "DELETE";
                break;
        }
        try {
            await fetch(link, {
                method: method,
                headers: {'Content-Type': 'application/json'}
            });
        } catch (error) {
            console.error('Error submitting request:', error);
            throw error;
        }
    };

    const navItems = getNavItems();

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

                    {/* Desktop Navigation */}
                    <nav className="hidden md:flex items-left gap-1">
                        {navItems.map((item) => (
                            <Link key={item.label} onClick={() => handleClickMenu(item.label)} href={"/"}
                                  className="px-3 py-2 text-sm font-medium hover:bg-muted rounded-md">
                                {item.label}
                            </Link>
                        ))}
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
