"use client"

import type {UserRole} from "@/lib/types"

/**
 * Badge vai trò ở header (giữ lại theo Q&A KB-4.6 Q2 — RBAC thật để Phase 5).
 * Trước đây 2 helper nằm trong `lib/rbac.ts` (đã xoá); giữ đúng phần UI cần dùng.
 */
const ROLE_DISPLAY_NAMES: Record<UserRole, string> = {
    admin: "Administrator",
    developer: "Developer",
    document_manager: "Document Manager",
}

const ROLE_COLORS: Record<UserRole, string> = {
    admin: "bg-red-500",
    developer: "bg-blue-500",
    document_manager: "bg-green-500",
}

interface RoleBadgeProps {
    role: UserRole
    size?: "sm" | "md" | "lg"
}

export function RoleBadge({role, size = "md"}: RoleBadgeProps) {
    const displayName = ROLE_DISPLAY_NAMES[role]
    const colorClass = ROLE_COLORS[role]

    const sizeClasses = {
        sm: "px-2 py-1 text-xs",
        md: "px-3 py-1.5 text-sm",
        lg: "px-4 py-2 text-base",
    }

    return (
        <span
            className={`inline-flex items-center rounded-full font-medium text-white ${colorClass} ${sizeClasses[size]}`}>
            {displayName}
        </span>
    )
}
