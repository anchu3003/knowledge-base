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

// ------------------------------
// Documents & health (KB-4.5) — khớp endpoint thật của BE Phase 3
// ------------------------------

/** `GET /documents/status` — số **chunk** đang có trong vector store. */
export interface DocumentStatus {
    collection_name: string
    document_count: number
    /** `healthy` (có chunk) · `empty` (0 chunk) · `error` (Chroma lỗi — kèm `error`). */
    status: string
    error?: string
}

export interface SupportedFileInfo {
    name: string
    path: string
    size_mb: number
    extension: string
}

/** `GET /documents/folder-info` — đếm file trên đĩa (không suy từ số chunk). */
export interface FolderInfo {
    folder_path: string
    exists: boolean
    total_files?: number
    files_by_extension?: Record<string, number>
    supported_files_count?: number
    /** BE chỉ trả 20 file đầu để hiển thị. */
    supported_files?: SupportedFileInfo[]
    auto_load_enabled?: boolean
}

export interface ReadinessCheck {
    ok: boolean
    detail: string
}

/** `GET /ready` — `ok` (200) · `degraded` (200, thiếu/empty index) · `error` (503). */
export interface ReadinessStatus {
    status: string
    checks: Record<string, ReadinessCheck>
}

/** `GET /health` — liveness, luôn 200 khi process còn sống. */
export interface HealthStatus {
    status: string
    version: string
    uptime_seconds: number
}

/** `POST /documents/refresh` — re-index toàn bộ folder tài liệu. */
export interface DocumentsRefreshResult {
    success: boolean
    message: string
    processed_files: number
    total_chunks: number
    details?: Array<Record<string, unknown>>
}
