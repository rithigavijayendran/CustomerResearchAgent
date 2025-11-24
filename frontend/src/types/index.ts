// TypeScript type definitions for the application

export interface User {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
  settings?: {
    theme?: 'light' | 'dark';
  };
  createdAt?: string;
}

export interface Chat {
  id: string;
  userId: string;
  title: string;
  createdAt: string;
  lastMessageAt?: string;
}

export interface Message {
  id: string;
  chatId: string;
  userId: string;
  role: 'user' | 'assistant';
  content: string;
  attachments: Array<{
    type: string;
    url: string;
    name: string;
  }>;
  sources: Array<{
    url: string;
    type: string;
    confidence: number;
  }>;
  metadata: Record<string, any>;
  createdAt: string;
  tokens?: number;
}

export interface AccountPlan {
  id: string;
  userId: string;
  chatId?: string;
  companyName: string;
  planJSON: {
    company_overview?: string;
    market_summary?: string;
    key_insights?: string;
    pain_points?: string;
    opportunities?: string;
    competitor_analysis?: string;
    swot?: {
      strengths?: string;
      weaknesses?: string;
      opportunities?: string;
      threats?: string;
    };
    strategic_recommendations?: string;
    final_account_plan?: string;
    [key: string]: any;
  };
  versions: PlanVersion[];
  sources: Array<{
    url: string;
    type: string;
    confidence: number;
  }>;
  status: 'draft' | 'published' | 'archived';
  createdAt: string;
  updatedAt: string;
}

export interface PlanVersion {
  versionId: string;
  timestamp: string;
  userId: string;
  changes: {
    section: string;
    oldContent?: string;
    newContent?: string;
  };
  diff?: Record<string, any>;
}

export interface MemorySummary {
  summary: string;
  keyInsights: string[];
  updatedAt: string;
}

export interface ChatListResponse {
  chats: Chat[];
  total: number;
  page: number;
  per_page: number;
  has_more: boolean;
}

export interface MessageListResponse {
  messages: Message[];
  total: number;
  page: number;
  per_page: number;
  cursor?: string;
  has_more: boolean;
}

export interface WebSocketMessage {
  type: 'token' | 'progress' | 'complete' | 'error';
  token?: string;
  text?: string;
  message?: string;
  timestamp?: string;
}

export interface UploadSession {
  uploadId: string;
  chunkSize: number;
}

export interface ApiError {
  error: string;
  message: string;
  detail?: string;
}

