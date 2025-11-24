// API client with TypeScript
import axios from 'axios';
import type { 
  User, Chat, Message, AccountPlan, 
  ChatListResponse, MessageListResponse, MemorySummary,
  UploadSession, PlanVersion
} from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle rate limit errors gracefully
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle rate limit errors (429)
    if (error.response?.status === 429) {
      console.warn('Rate limit exceeded. Please wait a moment before trying again.');
      // Don't throw error for rate limits - let components handle it gracefully
      return Promise.reject({
        ...error,
        isRateLimit: true,
        message: 'Rate limit exceeded. Please wait a moment and try again.'
      });
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  register: async (name: string, email: string, password: string): Promise<User> => {
    const response = await api.post('/api/auth/register', { name, email, password });
    return response.data;
  },
  
  login: async (email: string, password: string): Promise<{ access_token: string; user: User }> => {
    const response = await api.post('/api/auth/login', { email, password });
    localStorage.setItem('token', response.data.access_token);
    return response.data;
  },
  
  getProfile: async (): Promise<User> => {
    const response = await api.get('/api/auth/profile');
    return response.data;
  },
  
  updateProfile: async (data: Partial<User> & { oldPassword?: string; newPassword?: string }): Promise<User> => {
    const response = await api.put('/api/auth/profile', data);
    return response.data;
  },
  
  uploadAvatar: async (file: File): Promise<{ avatarUrl: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/auth/profile/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  
  logout: () => {
    localStorage.removeItem('token');
  },
  
  forgotPassword: async (email: string): Promise<{ message: string; success: boolean }> => {
    const response = await api.post('/api/auth/forgot-password', { email });
    return response.data;
  },
  
  resetPassword: async (token: string, newPassword: string): Promise<{ message: string; success: boolean }> => {
    const response = await api.post('/api/auth/reset-password', { token, new_password: newPassword });
    return response.data;
  },
};

// Chat API
export const chatApi = {
  listChats: async (page = 1, perPage = 20): Promise<ChatListResponse> => {
    const response = await api.get('/api/chats', { params: { page, per_page: perPage } });
    return response.data;
  },
  
  createChat: async (title?: string): Promise<Chat> => {
    const response = await api.post('/api/chats', { title });
    return response.data;
  },
  
  getMessages: async (chatId: string, page = 1, perPage = 50, cursor?: string): Promise<MessageListResponse> => {
    const response = await api.get(`/api/chats/${chatId}/messages`, {
      params: { page, per_page: perPage, cursor },
    });
    return response.data;
  },
  
  sendMessage: async (chatId: string, content: string, attachments: any[] = []): Promise<Message> => {
    const response = await api.post(`/api/chats/${chatId}/messages`, {
      content,
      role: 'user',
      attachments,
    });
    return response.data;
  },
  
  getMemory: async (chatId: string): Promise<MemorySummary> => {
    const response = await api.get(`/api/chats/${chatId}/memory`);
    return response.data;
  },
  
  deleteChat: async (chatId: string): Promise<{ message: string; deleted: boolean }> => {
    const response = await api.delete(`/api/chats/${chatId}`);
    return response.data;
  },
};

// Plan API
export const planApi = {
  listPlans: async (): Promise<{ plans: any[] }> => {
    const response = await api.get('/api/account-plan/list');
    return response.data;
  },
  
  getPlan: async (planId: string): Promise<AccountPlan> => {
    const response = await api.get(`/api/plans/${planId}`);
    return response.data;
  },
  
  getPlanByChat: async (chatId: string): Promise<AccountPlan | null> => {
    try {
      const response = await api.get(`/api/plans/by-chat/${chatId}`);
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null; // No plan for this chat yet
      }
      throw error;
    }
  },
  
  updateSection: async (planId: string, sectionKey: string, content: string): Promise<any> => {
    const response = await api.put(`/api/plans/${planId}/section/${sectionKey}`, { content });
    return response.data;
  },
  
  regenerateSection: async (planId: string, sectionKey: string): Promise<{
    section: string;
    content: string;
    sources: Array<any>;
    confidence: number;
    versionId: string;
  }> => {
    const response = await api.post(`/api/plans/${planId}/section/${sectionKey}/regenerate`);
    return response.data;
  },
  
  downloadPDF: async (planId: string): Promise<Blob> => {
    const response = await api.get(`/api/plans/${planId}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },
  
  deletePlan: async (planId: string): Promise<{ message: string; deleted: boolean }> => {
    const response = await api.delete(`/api/plans/${planId}`);
    return response.data;
  },
};

// Upload API
export const uploadApi = {
  initUpload: async (companyName?: string, chatId?: string): Promise<UploadSession> => {
    const params = new URLSearchParams();
    if (companyName) params.append('company_name', companyName);
    if (chatId) params.append('chat_id', chatId);
    
    const url = `/api/uploads/init${params.toString() ? '?' + params.toString() : ''}`;
    try {
      const response = await api.post(url);
      return response.data;
    } catch (error: any) {
      console.error('initUpload error:', error);
      throw error;
    }
  },
  
  uploadChunk: async (uploadId: string, chunkIndex: number, totalChunks: number, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_index', chunkIndex.toString());
    formData.append('total_chunks', totalChunks.toString());
    
    const response = await api.post(`/api/uploads/${uploadId}/chunk`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  
  completeUpload: async (uploadId: string, companyName?: string, chatId?: string): Promise<{ uploadId: string; status: string; jobId?: string }> => {
    const body = {
      companyName: companyName || '',
      chatId: chatId || ''
    };
    try {
      const response = await api.post(`/api/uploads/${uploadId}/complete`, body);
      return response.data;
    } catch (error: any) {
      throw error;
    }
  },
};

export default api;

