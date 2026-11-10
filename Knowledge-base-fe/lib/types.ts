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
    /** KB-5.4: câu hỏi nhiều ý được tách thành các phần này (rỗng/không có = retrieve 1 bước). */
    multi_query_parts?: string[]
    multi_query_enabled?: boolean
    /** KB-9.4: số nguồn bị loại vì điểm rerank dưới ngưỡng liên quan. */
    dropped_sources?: number
    /** KB-9.4: ngưỡng đang áp dụng (0 = tắt lọc). */
    relevance_min_score?: number
    [key: string]: unknown
}

/** Một message trong khung chat (client-side; BE chỉ giữ `conversation_id` + history nội bộ). */
export interface ChatMessage {
    id: string
    role: 'user' | 'assistant'
    content: string
    /** Nguồn của câu trả lời — render bằng `SourcesPanel` (KB-4.3). Field `citations` cũ đã xoá ở KB-5.6. */
    sources?: ChatSource[]
    metadata?: ChatMetadata
    /** Đang stream token (KB-4.4) — không lưu vào `localStorage`. */
    isStreaming?: boolean
    /** Người dùng bấm Stop giữa lúc stream (KB-4.4). */
    stopped?: boolean
    /** `end.answer` rỗng ⇒ hiện giải thích + nút Thử lại thay vì bubble trống (KB-4.11). */
    emptyAnswer?: boolean
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

/** `POST /documents/sync` — index **tăng dần** (KB-5.1): chỉ file mới/đổi, xoá chunk của file đã bỏ. */
export interface DocumentsSyncResult {
    success: boolean
    message: string
    /** Tên file (không phải path) — đủ để hiện cho người dùng. */
    added: string[]
    updated: string[]
    removed: string[]
    /** File bị bỏ qua vì quá size / không đọc được. */
    skipped: Array<{ path: string; reason: string }>
    unchanged: number
    total_chunks: number
    removed_chunks: number
    elapsed_ms: number
    details?: string[]
}

/**
 * Lịch sử hội thoại bền phía server (KB-5.2).
 *
 * `content` là bản **BE đã redact PII** trước khi lưu ⇒ reload từ server có thể thấy placeholder
 * `[REDACTED:EMAIL]` thay cho dữ liệu thật. Đó là hành vi cố ý (không lưu PII thô).
 */
export interface ConversationMessage {
    role: 'user' | 'assistant' | string
    content: string
    timestamp: string
    interrupted?: boolean
}

export interface ConversationSummary {
    id: string
    title: string
    created_at: string
    updated_at: string
    message_count: number
}

export interface ConversationsListResponse {
    conversations: ConversationSummary[]
    total: number
}

export interface ConversationDetail {
    id: string
    title: string
    created_at: string
    updated_at: string
    messages: ConversationMessage[]
}

// ------------------------------
// KB-9.4: cấu hình chỉnh được lúc chạy (`GET /settings`)
// ------------------------------
export interface RuntimeSetting {
    key: string
    kind: 'int' | 'float' | 'bool'
    min: number | null
    max: number | null
    description: string
}

export interface SettingsResponse {
    /** Giá trị đang có hiệu lực. */
    values: Record<string, number | boolean>
    /** Giá trị mặc định của server (env lúc khởi động). */
    defaults: Record<string, number | boolean>
    /** Tham số người dùng đã đổi (khác default). */
    overridden: string[]
    tunables: RuntimeSetting[]
}
