import type React from "react"
// User and role type definitions for OnboardAI

export type UserRole = "admin" | "developer" | "document_manager"

export interface User {
    id: string
    email: string
    name: string
    role: UserRole
    createdAt: Date
    lastLogin?: Date
}

export interface AuthContextType {
    user: User | null
    isLoading: boolean
    isAuthenticated: boolean
    login: (email: string, password: string, role: UserRole) => Promise<void>
    logout: () => Promise<void>
    setUser: (user: User | null) => void
}

export interface Permission {
    action: string
    requiredRoles: UserRole[]
}

export interface ProtectedRouteProps {
    requiredRoles: UserRole[]
    children: React.ReactNode
    fallback?: React.ReactNode
}

export interface Feedback {
    id: string
    userId: string
    category: "bug" | "suggestion" | "feature_request"
    message: string
    sentiment?: "positive" | "negative" | "neutral"
    createdAt: Date
    resolved?: boolean
}

export interface FeedbackContextType {
    feedbacks: Feedback[]
    addFeedback: (feedback: Omit<Feedback, "id" | "createdAt">) => Promise<void>
    isLoading: boolean
}

export interface DocumentTemplate {
    id: string
    name: string
    description: string
    category: "setup_guide" | "api_docs" | "git_workflow" | "testing_checklist" | "business_overview"
    createdAt: Date
    updatedAt: Date
}

export interface Document {
    id: string
    title: string
    templateId: string
    uploadedBy: string
    uploadedByName: string
    content: string
    status: "pending" | "approved" | "rejected"
    createdAt: Date
    updatedAt: Date
    approvedBy?: string
    rejectionReason?: string
}

export interface ReindexJob {
    id: string
    status: "pending" | "in_progress" | "completed" | "failed"
    startedAt: Date
    completedAt?: Date
    progress: number
    totalDocuments: number
    processedDocuments: number
    failedDocuments: number
    errorMessage?: string
    initiatedBy: string
}

// ------------------------------
// Chat / API contract (KB-4.1) — khớp backend Phase 3
// ------------------------------

/** Một nguồn RAG trả về (mỗi **chunk** một phần tử — xem KB-2.3). */
export interface ChatSource {
    file_path: string
    file_name: string
    file_type: string
    relevance_score: number
    /** Bản cũ (BE ≤ KB-2.2) — vẫn khai báo để không vỡ nếu BE cũ. */
    content_preview?: string
    /** KB-2.3: nhãn `[S#]` map 1-1 với chip trong câu trả lời. */
    citation_id?: string
    chunk_id?: string
    heading_path?: string
    snippet?: string
}

export interface ChatMetadata {
    retrieved_documents?: number
    timestamp?: string
    model?: string
    temperature?: number
    max_tokens?: number
    pii_redacted?: boolean
    pii_redacted_count?: number
    query_rewrite_attempts?: number
    [key: string]: unknown
}

export interface ChatRequest {
    message: string
    conversation_id?: string
    max_tokens?: number
    temperature?: number
}

export interface ChatResponse {
    response: string
    conversation_id: string
    sources?: ChatSource[]
    metadata?: ChatMetadata
}
