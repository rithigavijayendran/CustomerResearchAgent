// ChatGPT-like Chat Window Component - Complete Implementation
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Virtuoso, VirtuosoHandle } from 'react-virtuoso';
import { Paperclip, Mic, Send, Copy, RefreshCw, ThumbsUp, ThumbsDown, Sparkles, Save, FileText, Download, Edit2, Trash2 } from 'lucide-react';
import { chatApi, planApi } from '../lib/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { useVoice } from '../hooks/useVoice';
import { useChunkedUpload } from '../hooks/useChunkedUpload';
import { useTheme } from '../hooks/useTheme';
import type { Message, AccountPlan } from '../types';
import ReactMarkdown from 'react-markdown';

interface ChatWindowProps {
  chatId: string | null;
  onNewChat: () => void;
  onChatCreated?: (chatId: string) => void;
  onPlanUpdated?: () => void;
}

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  streamingText?: string;
  isEphemeral?: boolean;
  onCopy?: () => void;
  onRegenerate?: () => void;
  onAddToPlan?: () => void;
  onLike?: () => void;
  onDislike?: () => void;
}

function MessageBubble({
  message,
  isStreaming = false,
  streamingText = '',
  isEphemeral = false,
  onCopy,
  onRegenerate,
  onAddToPlan,
  onLike,
  onDislike,
}: MessageBubbleProps) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const isUser = message.role === 'user';
  const displayContent = isStreaming && streamingText ? streamingText : message.content;

  return (
    <div className={`group w-full ${isEphemeral ? 'opacity-75' : ''}`}>
      <div className="max-w-3xl mx-auto px-4 py-6">
        <div className={`flex gap-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
          {/* Avatar */}
          <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
            isUser ? 'bg-blue-600' : 'bg-blue-500'
          }`}>
            {isUser ? (
              <span className="text-white text-sm font-semibold">U</span>
            ) : (
              <span className="text-white text-sm font-semibold">AI</span>
            )}
          </div>

          {/* Message Content */}
          <div className={`flex-1 ${isUser ? 'text-right' : 'text-left'}`}>
            <div className={`inline-block max-w-[85%] ${isUser ? 'text-left' : ''}`}>
              {/* Display attachments if any */}
              {message.attachments && message.attachments.length > 0 && (
                <div className="mb-3 space-y-2">
                  {message.attachments.map((attachment, idx) => (
                    <div
                      key={idx}
                      className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-lg transition-colors ${
                        isDark 
                          ? 'bg-blue-900/30 border border-blue-800 hover:bg-blue-900/50' 
                          : 'bg-blue-50 border border-blue-200 hover:bg-blue-100'
                      }`}
                    >
                      <FileText size={18} className={`flex-shrink-0 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                      <span className={`text-sm font-medium ${isDark ? 'text-blue-200' : 'text-blue-900'}`}>{attachment.name}</span>
                      <span className={`text-xs ${isDark ? 'text-blue-400' : 'text-blue-600'}`}>(Uploaded)</span>
                    </div>
                  ))}
                </div>
              )}
              
              {isUser ? (
                <div className={`whitespace-pre-wrap break-words font-medium leading-relaxed ${
                  isDark ? 'text-gray-100' : 'text-gray-900'
                }`}>
                  {message.content}
                </div>
              ) : (
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  <div className={`whitespace-pre-wrap break-words leading-relaxed ${
                    isDark ? 'text-gray-200' : 'text-gray-900'
                  }`}>
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className={isDark ? 'text-gray-200' : 'text-gray-900'} style={{ marginBottom: '0.5rem' }}>{children}</p>,
                      ul: ({ children }) => <ul className={isDark ? 'text-gray-200' : 'text-gray-900'} style={{ marginBottom: '0.5rem' }}>{children}</ul>,
                      ol: ({ children }) => <ol className={isDark ? 'text-gray-200' : 'text-gray-900'} style={{ marginBottom: '0.5rem' }}>{children}</ol>,
                      li: ({ children }) => <li className={isDark ? 'text-gray-200' : 'text-gray-900'}>{children}</li>,
                      h1: ({ children }) => <h1 className={isDark ? 'text-white' : 'text-gray-900'} style={{ fontSize: '1.5rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>{children}</h1>,
                      h2: ({ children }) => <h2 className={isDark ? 'text-white' : 'text-gray-900'} style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>{children}</h2>,
                      h3: ({ children }) => <h3 className={isDark ? 'text-white' : 'text-gray-900'} style={{ fontSize: '1.125rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>{children}</h3>,
                      code: ({ children }) => <code className={isDark ? 'text-gray-200 bg-gray-700' : 'text-gray-900 bg-gray-100'} style={{ padding: '0.125rem 0.25rem', borderRadius: '0.25rem' }}>{children}</code>,
                      pre: ({ children }) => <pre className={isDark ? 'text-gray-200 bg-gray-800' : 'text-gray-900 bg-gray-100'} style={{ padding: '0.5rem', borderRadius: '0.25rem', overflow: 'auto' }}>{children}</pre>,
                      strong: ({ children }) => <strong className={isDark ? 'text-white' : 'text-gray-900'} style={{ fontWeight: 'bold' }}>{children}</strong>,
                      em: ({ children }) => <em className={isDark ? 'text-gray-300' : 'text-gray-900'} style={{ fontStyle: 'italic' }}>{children}</em>,
                      a: ({ children, href }) => <a href={href} className="text-blue-400 hover:text-blue-300" style={{ textDecoration: 'underline' }}>{children}</a>,
                    }}
                  >
                    {displayContent}
                  </ReactMarkdown>
                  </div>
                  {isStreaming && <span className={`animate-pulse inline-block w-2 h-4 ml-1 ${isDark ? 'bg-blue-400' : 'bg-blue-500'}`}>▊</span>}
                </div>
              )}

              {/* Message Actions (for assistant messages) */}
              {!isUser && !isStreaming && !isEphemeral && (
                <div className="flex items-center gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={onCopy}
                    className={`p-1.5 rounded transition-colors ${
                      isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-200'
                    }`}
                    title="Copy"
                  >
                    <Copy size={14} className={isDark ? 'text-gray-400' : 'text-gray-600'} />
                  </button>
                  <button
                    onClick={onRegenerate}
                    className={`p-1.5 rounded transition-colors ${
                      isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-200'
                    }`}
                    title="Regenerate"
                  >
                    <RefreshCw size={14} className={isDark ? 'text-gray-400' : 'text-gray-600'} />
                  </button>
                  <button
                    onClick={onAddToPlan}
                    className={`p-1.5 rounded transition-colors ${
                      isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-200'
                    }`}
                    title="Add to Plan"
                  >
                    <FileText size={14} className={isDark ? 'text-gray-400' : 'text-gray-600'} />
                  </button>
                  <button
                    onClick={onLike}
                    className={`p-1.5 rounded transition-colors ${
                      isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-200'
                    }`}
                    title="Good response"
                  >
                    <ThumbsUp size={14} className={isDark ? 'text-gray-400' : 'text-gray-600'} />
                  </button>
                  <button
                    onClick={onDislike}
                    className={`p-1.5 rounded transition-colors ${
                      isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-200'
                    }`}
                    title="Bad response"
                  >
                    <ThumbsDown size={14} className={isDark ? 'text-gray-400' : 'text-gray-600'} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}



export function ChatWindow({ chatId, onNewChat, onChatCreated, onPlanUpdated }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [ephemeralMessages, setEphemeralMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [hasMore, setHasMore] = useState(true);
  const [page, setPage] = useState(1);
  const [cursor, setCursor] = useState<string | undefined>();
  const [isComposing, setIsComposing] = useState(false);
  // Memory summarization removed per user request
  const [accountPlan, setAccountPlan] = useState<AccountPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [isResearching, setIsResearching] = useState(false);
  const [researchProgress, setResearchProgress] = useState<string>('');
  const [documentUploaded, setDocumentUploaded] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string>('');
  const [uploadChatId, setUploadChatId] = useState<string | null>(null);
  
  // Get company name from account plan or session for upload
  const [uploadCompanyName, setUploadCompanyName] = useState<string | undefined>();
  
  useEffect(() => {
    // Try to get company name from account plan
    if (accountPlan?.companyName) {
      setUploadCompanyName(accountPlan.companyName);
    }
  }, [accountPlan]);
  
  const { uploading: isUploading, progress: uploadProgress, uploadFile } = useChunkedUpload({
    companyName: uploadCompanyName,
    chatId: chatId || undefined,
    onProgress: (progress) => {
      // Don't show research banner for upload progress
      setResearchProgress(`📤 Uploading document... ${Math.round(progress)}%`);
    },
    onComplete: async (uploadId, jobId) => {
      // Clear research progress immediately - don't show "Agent is researching..."
      setIsResearching(false);
      setResearchProgress('');
      
      // Set document uploaded state to show professional confirmation
      setDocumentUploaded(true);
      
      // Clear ephemeral messages from upload process
      setEphemeralMessages([]);
      
      // Create a message in the chat showing the uploaded document
      // The filename is stored in uploadedFileName state
      // Use uploadChatId from state (set during file upload) or current chatId
      const currentChatId = uploadChatId || chatId;
      if (uploadedFileName && currentChatId) {
        try {
          // Save message to backend for persistence
          await chatApi.sendMessage(currentChatId, `📄 Uploaded document: ${uploadedFileName}`, [{
            type: 'file',
            url: '',
            name: uploadedFileName
          }]);
          
          // Reload messages to get the saved message from backend
          const data = await chatApi.getMessages(currentChatId, 1, 50);
          if (data.messages.length > 0) {
            const sortedMessages = data.messages.sort((a, b) => 
              new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
            );
            setMessages(sortedMessages);
          }
          
          // Clear upload chatId after use
          setUploadChatId(null);
        } catch (error) {
          console.error('Failed to save upload message to backend:', error);
        }
      }
    },
    onError: (error) => {
      setIsResearching(false);
      setResearchProgress('');
      setDocumentUploaded(false);
      onProgress(`❌ Upload failed: ${error}`);
    },
  });
  
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollPositionRef = useRef<number>(0);

  // Memory summarization removed per user request

  // Handle progress messages as ephemeral
  const onProgress = useCallback((message: string) => {
    // Don't show research banner for upload-related messages
    const uploadKeywords = ['upload', 'uploading', 'processing document', 'file uploaded'];
    const isUploadMessage = uploadKeywords.some(keyword => 
      message.toLowerCase().includes(keyword)
    );
    
    if (isUploadMessage) {
      // Don't create ephemeral messages or show research banner for uploads
      // Upload completion is handled separately in useChunkedUpload onComplete
      return;
    }
    
    // Check if this is a research-related progress message (only after user asks a question)
    const researchKeywords = ['research', 'searching', 'analyzing', 'gathering', 'generating', 'plan', 'agent'];
    const isResearchMessage = researchKeywords.some(keyword => 
      message.toLowerCase().includes(keyword)
    );
    
    if (isResearchMessage && !message.includes('✅') && !message.includes('Complete')) {
      setIsResearching(true);
      setResearchProgress(message);
    }
    
    // If message indicates completion, stop researching
    if (message.includes('✅') || message.includes('Complete') || message.includes('ready') || message.includes('Done')) {
      setIsResearching(false);
      setResearchProgress('');
    }
    
    const ephemeralMsg: Message = {
      id: `ephemeral-${Date.now()}`,
      chatId: chatId || '',
      userId: '',
      role: 'assistant',
      content: message,
      attachments: [],
      sources: [],
      metadata: { ephemeral: true },
      createdAt: new Date().toISOString(),
    };
    
    setEphemeralMessages((prev) => {
      // Remove old ephemeral messages (keep last 3)
      const recent = [...prev, ephemeralMsg].slice(-3);
      return recent;
    });

    // Auto-remove after 5 seconds
    setTimeout(() => {
      setEphemeralMessages((prev) => prev.filter(m => m.id !== ephemeralMsg.id));
    }, 5000);
  }, [chatId]);

  // Load account plan for this chat
  const loadAccountPlan = useCallback(async () => {
    if (!chatId) return;
    try {
      setPlanLoading(true);
      const plan = await planApi.getPlanByChat(chatId);
      setAccountPlan(plan);
    } catch (error) {
      console.error('Error loading account plan:', error);
      setAccountPlan(null);
    } finally {
      setPlanLoading(false);
    }
  }, [chatId]);

  const onComplete = useCallback(async (text: string) => {
    // Clear research state immediately when response is complete
    setIsResearching(false);
    setResearchProgress('');
    
    // Clear ephemeral messages (like "Analyzing your request...")
    setEphemeralMessages([]);
    
    if (chatId) {
      try {
        // Reload all messages to ensure correct order
        const data = await chatApi.getMessages(chatId, 1, 50);
        if (data.messages.length > 0) {
          // Sort by createdAt to maintain correct chronological order
          const sortedMessages = data.messages.sort((a, b) => 
            new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          );
          setMessages(sortedMessages);
        }
        // Reload account plan when message completes
        await loadAccountPlan();
      } catch (error) {
        console.error('Failed to load new message:', error);
      }
    }
  }, [chatId, loadAccountPlan]);

  const onError = useCallback((error: string) => {
    console.error('WebSocket error:', error);
  }, []);

  // Track the actual chatId being used (may be different from prop during new chat creation)
  const [activeChatId, setActiveChatId] = useState<string | null>(chatId);
  
  useEffect(() => {
    // Update activeChatId when chatId prop changes
    setActiveChatId(chatId);
  }, [chatId]);

  const { isConnected, streamingText, sendMessage, connect, isActuallyConnected } = useWebSocket({
    chatId: activeChatId || '',
    onToken: () => {},
    onProgress,
    onComplete,
    onError,
    onPlanUpdated: async (planId, companyName) => {
      // Reload account plan when it's updated
      if (activeChatId) {
        try {
          const plan = await planApi.getPlanByChat(activeChatId);
          setAccountPlan(plan);
          onProgress(`✅ Account plan updated for ${companyName}`);
          // Notify parent to reload chats (to update chat title)
          if (onPlanUpdated) {
            onPlanUpdated();
          }
        } catch (error) {
          console.error('Error loading updated account plan:', error);
        }
      }
    },
  });

  const { isListening, startListening, stopListening, speak } = useVoice({
    onTranscript: (text, isFinal) => {
      if (isFinal) {
        setInput(text);
      } else {
        // Stream interim transcripts to input
        setInput(text);
      }
    },
  });

  const loadMessages = useCallback(async (pageNum: number, cursorParam?: string) => {
    if (!chatId) return;
    try {
      const data = await chatApi.getMessages(chatId, pageNum, 50, cursorParam);
      setMessages((prev) => {
        // Prepend older messages and sort by createdAt to maintain order
        const existingIds = new Set(prev.map(m => m.id));
        const newMessages = data.messages.filter(m => !existingIds.has(m.id));
        const allMessages = [...newMessages.reverse(), ...prev];
        // Sort by createdAt to ensure correct chronological order
        return allMessages.sort((a, b) => 
          new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        );
      });
      setHasMore(data.has_more);
      setCursor(data.cursor);
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  }, [chatId]);

  // Upward infinite scroll
  const handleStartReached = useCallback(() => {
    if (hasMore && chatId) {
      const nextPage = page + 1;
      setPage(nextPage);
      loadMessages(nextPage, cursor);
    }
  }, [hasMore, page, cursor, loadMessages, chatId]);

  useEffect(() => {
    if (chatId) {
      setMessages([]);
      setPage(1);
      setCursor(undefined);
      loadMessages(1);
      loadAccountPlan();
    } else {
      setMessages([]);
      setAccountPlan(null);
    }
    
    // Clear document uploaded state when switching chats
    setDocumentUploaded(false);
    setUploadedFileName('');
  }, [chatId]);


  // Restore scroll position
  useEffect(() => {
    if (virtuosoRef.current && scrollPositionRef.current > 0) {
      virtuosoRef.current.scrollToIndex({
        index: Math.floor(scrollPositionRef.current / 100),
        align: 'start',
      });
      scrollPositionRef.current = 0;
    }
  }, [messages.length]);

  const handleSend = useCallback(async () => {
    if (!input.trim()) return;

    // Clear document uploaded state when user sends a message
    setDocumentUploaded(false);
    setUploadedFileName('');

    // If no chatId, create a new chat first
    let currentChatId = chatId;
    if (!currentChatId) {
      try {
        const newChat = await chatApi.createChat();
        currentChatId = newChat.id;
        // Update activeChatId immediately so WebSocket can connect
        setActiveChatId(currentChatId);
        // Notify parent component to update chatId
        if (onChatCreated) {
          onChatCreated(currentChatId);
        }
        // Wait a moment for activeChatId to propagate to useWebSocket hook
        await new Promise(resolve => setTimeout(resolve, 300));
      } catch (error) {
        console.error('Failed to create chat:', error);
        onProgress('❌ Failed to create chat. Please try again.');
        return;
      }
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      chatId: currentChatId || '',
      userId: '',
      role: 'user',
      content: input,
      attachments: [],
      sources: [],
      metadata: {},
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const messageText = input;
    setInput('');
    
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    // Set researching state for research-related messages
    const isResearchQuery = messageText.toLowerCase().includes('research') || 
                            messageText.toLowerCase().includes('analyze') ||
                            messageText.toLowerCase().startsWith('research');
    if (isResearchQuery) {
      setIsResearching(true);
      setResearchProgress('🔍 Agent is researching...');
    }
    
    // CRITICAL: Agent only processes messages via WebSocket, not API
    // So we MUST use WebSocket. For new chats, force connection and wait.
    if (currentChatId && !chatId) {
      // New chat was just created - force WebSocket connection and wait
      // Force connection attempt
      if (connect) {
        connect();
      }
      
      // Wait for WebSocket to connect (up to 5 seconds)
      let attempts = 0;
      const maxAttempts = 25; // Wait up to 5 seconds
      
      while (attempts < maxAttempts && !isActuallyConnected()) {
        await new Promise(resolve => setTimeout(resolve, 200));
        attempts++;
      }
      
      if (isActuallyConnected()) {
        sendMessage(messageText);
      } else {
        onProgress('❌ Failed to connect. Please refresh and try again.');
        setIsResearching(false);
        setResearchProgress('');
        // Still save the message to database
        try {
          await chatApi.sendMessage(currentChatId, messageText);
        } catch (error) {
          // Silent error handling
        }
      }
    } else if (currentChatId && isConnected) {
      // Existing chat with WebSocket connected - send immediately
      sendMessage(messageText);
    } else if (currentChatId) {
      // Have chatId but WebSocket not connected - try to connect first
      if (connect) {
        connect();
      }
      
      // Wait a bit for connection
      let attempts = 0;
      const maxAttempts = 10;
      while (attempts < maxAttempts && !isActuallyConnected()) {
        await new Promise(resolve => setTimeout(resolve, 200));
        attempts++;
      }
      
      if (isActuallyConnected()) {
        sendMessage(messageText);
      } else {
        onProgress('❌ Connection failed. Please refresh and try again.');
        setIsResearching(false);
        setResearchProgress('');
      }
    }
  }, [input, chatId, isConnected, sendMessage, onProgress, onChatCreated]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
  };

  const handleFileUpload = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      return;
    }

    // If no chatId, create a new chat first
    let currentUploadChatId = chatId;
    if (!currentUploadChatId) {
      try {
        onProgress('📝 Creating new chat for file upload...');
        const newChat = await chatApi.createChat();
        currentUploadChatId = newChat.id;
        // Store in state for use in onComplete callback
        setUploadChatId(newChat.id);
        if (onChatCreated) {
          onChatCreated(newChat.id);
        }
        onProgress('✅ Chat created. Starting upload...');
      } catch (error) {
        onProgress('❌ Failed to create chat. Please try again.');
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }
    } else {
      // Store in state for use in onComplete callback
      setUploadChatId(currentUploadChatId);
    }

    // Validate file type
    const allowedTypes = ['.pdf', '.doc', '.docx', '.txt'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedTypes.includes(fileExtension)) {
      onProgress(`❌ Invalid file type. Please upload: ${allowedTypes.join(', ')}`);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    // Validate file size (max 50MB)
    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
      onProgress(`❌ File too large. Maximum size is 50MB. Your file is ${(file.size / 1024 / 1024).toFixed(2)}MB`);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    try {
      // Store filename for display
      setUploadedFileName(file.name);
      
      // Upload file with the current chatId and companyName
      await uploadFile(file, 5 * 1024 * 1024, currentUploadChatId || undefined, uploadCompanyName);
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || 'Upload failed';
      onProgress(`❌ Upload failed: ${errorMsg}`);
    }
    
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleAddToPlan = useCallback((messageId: string) => {
    const message = messages.find(m => m.id === messageId);
    if (message && chatId) {
      onProgress(`📝 Adding message to account plan...`);
      sendMessage(`Add this to account plan: ${message.content}`);
    }
  }, [messages, chatId, onProgress, sendMessage]);

  const handleEditPlanSection = useCallback((sectionKey: string) => {
    if (chatId) {
      sendMessage(`Edit account plan section ${sectionKey}`);
    }
  }, [chatId, sendMessage]);

  const handleRegeneratePlanSection = useCallback((sectionKey: string) => {
    if (chatId) {
      sendMessage(`Regenerate account plan section ${sectionKey}`);
    }
  }, [chatId, sendMessage]);

  const handleAddPlanField = useCallback(() => {
    if (chatId) {
      const fieldName = prompt('Enter field name:');
      if (fieldName) {
        sendMessage(`Add field ${fieldName} to account plan`);
      }
    }
  }, [chatId, sendMessage]);

  const handleRemovePlanField = useCallback((fieldName: string) => {
    if (chatId && confirm(`Remove field "${fieldName}"?`)) {
      sendMessage(`Remove field ${fieldName} from account plan`);
    }
  }, [chatId, sendMessage]);

  const handleDownloadPlanPDF = useCallback(async () => {
    if (!accountPlan?.id) return;
    try {
      const blob = await planApi.downloadPDF(accountPlan.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${accountPlan.companyName || 'AccountPlan'}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      onProgress('✅ PDF downloaded successfully!');
    } catch (error) {
      onProgress('❌ Failed to download PDF');
    }
  }, [accountPlan, onProgress]);

  // Listen for plan action events (must be after function definitions)
  useEffect(() => {
    const handleEditSection = (e: CustomEvent) => {
      handleEditPlanSection(e.detail.section);
    };
    const handleRegenerateSection = (e: CustomEvent) => {
      handleRegeneratePlanSection(e.detail.section);
    };
    const handleDownloadPDF = () => {
      handleDownloadPlanPDF();
    };

    window.addEventListener('editPlanSection', handleEditSection as EventListener);
    window.addEventListener('regeneratePlanSection', handleRegenerateSection as EventListener);
    window.addEventListener('downloadPlanPDF', handleDownloadPDF);

    return () => {
      window.removeEventListener('editPlanSection', handleEditSection as EventListener);
      window.removeEventListener('regeneratePlanSection', handleRegenerateSection as EventListener);
      window.removeEventListener('downloadPlanPDF', handleDownloadPDF);
    };
  }, [handleEditPlanSection, handleRegeneratePlanSection, handleDownloadPlanPDF]);

  const handleRegenerate = useCallback((messageId: string) => {
    const message = messages.find(m => m.id === messageId);
    if (message && chatId) {
      sendMessage(`Regenerate: ${message.content}`);
    }
  }, [messages, chatId, sendMessage]);

  // Combine messages with ephemeral
  const allMessages = useMemo(() => {
    return [...messages, ...ephemeralMessages];
  }, [messages, ephemeralMessages]);

  const currentStreamingMessage = streamingText ? {
    id: 'streaming',
    chatId: chatId || '',
    userId: '',
    role: 'assistant' as const,
    content: '',
    attachments: [],
    sources: [],
    metadata: {},
    createdAt: new Date().toISOString(),
  } : null;

  const displayMessages = currentStreamingMessage 
    ? [...allMessages, currentStreamingMessage]
    : allMessages;

  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div className={`flex flex-col h-full relative ${isDark ? 'bg-gray-900' : 'bg-white'}`}>
      {/* Account Plan Actions Bar - Shows when plan exists */}
      {accountPlan && (
        <div className="bg-blue-600 text-white px-4 py-3 border-b border-blue-700 shadow-md z-10">
          <div className="max-w-3xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText size={20} />
              <div>
                <div className="font-semibold text-sm">{accountPlan.companyName} - Account Plan</div>
                <div className="text-xs text-blue-200">
                  {accountPlan.updatedAt 
                    ? `Updated ${new Date(accountPlan.updatedAt).toLocaleDateString()}`
                    : 'Ready to edit'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleDownloadPlanPDF}
                className="px-3 py-1.5 bg-blue-700 hover:bg-blue-800 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors"
                title="Download PDF"
              >
                <Download size={14} />
                <span>PDF</span>
              </button>
              <button
                onClick={() => window.open(`/plans`, '_blank')}
                className="px-3 py-1.5 bg-blue-700 hover:bg-blue-800 rounded-lg text-xs font-medium transition-colors"
                title="View Full Plan"
              >
                View Full
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Research Loading Indicator - Only show when researching and not streaming */}
      {isResearching && allMessages.length > 0 && !streamingText && (
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-4 py-3 border-b border-blue-700 shadow-md z-10">
          <div className="max-w-3xl mx-auto flex items-center gap-3">
            <div className="relative">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              <div className="absolute inset-0 animate-ping rounded-full h-5 w-5 border border-white opacity-20"></div>
            </div>
            <div className="flex-1">
              <div className="font-semibold text-sm flex items-center gap-2">
                <Sparkles size={14} className="animate-pulse" />
                Agent is researching...
              </div>
              {researchProgress && (
                <div className="text-xs text-blue-100 mt-0.5 whitespace-pre-wrap">{researchProgress}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* User Input Required Indicator - Show when agent is asking for clarification */}
      {(() => {
        if (allMessages.length === 0 || isResearching || streamingText) return null;
        
        const lastMessage = allMessages[allMessages.length - 1];
        const needsInput = lastMessage && 
          lastMessage.role === 'assistant' && 
          (lastMessage.content.includes('conflicting information') || 
           lastMessage.content.includes('Should I dig deeper') ||
           lastMessage.content.includes('What would you like me to do'));
        
        if (!needsInput) return null;
        
        return (
          <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 shadow-sm z-10">
            <div className="max-w-3xl mx-auto flex items-center gap-2 text-yellow-800">
              <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
              <span className="text-xs font-medium">Waiting for your input...</span>
            </div>
          </div>
        );
      })()}

      {/* Main Chat Area */}
      <div className="flex-1 overflow-hidden">
        {allMessages.length === 0 && !currentStreamingMessage ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-2xl px-4">
              {documentUploaded ? (
                <div className="space-y-4">
                  <div className="flex justify-center mb-4">
                    <div className={`w-16 h-16 rounded-full flex items-center justify-center ${
                      isDark ? 'bg-green-900/30' : 'bg-green-100'
                    }`}>
                      <svg className={`w-8 h-8 ${isDark ? 'text-green-400' : 'text-green-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                  </div>
                  <h1 className={`text-3xl font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>
                    Document Uploaded Successfully
                  </h1>
                  <p className={`text-lg mb-1 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
                    <span className="font-medium">{uploadedFileName}</span>
                  </p>
                  <p className={`text-base mb-6 ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    Your document has been processed and is ready for analysis.
                  </p>
                  <div className={`${isDark ? 'bg-blue-900/30 border-blue-800' : 'bg-blue-50 border-blue-200'} border rounded-lg p-4 text-left`}>
                    <p className={`text-sm font-medium mb-2 ${isDark ? 'text-blue-300' : 'text-blue-900'}`}>What would you like to do next?</p>
                    <ul className={`text-sm space-y-1 list-disc list-inside ${isDark ? 'text-blue-200' : 'text-blue-800'}`}>
                      <li>Ask questions about the document content</li>
                      <li>Generate an account plan from the document</li>
                      <li>Request specific insights or analysis</li>
                    </ul>
                  </div>
                </div>
              ) : (
                <h1 className={`text-4xl font-semibold mb-3 ${isDark ? 'text-white' : 'text-blue-900'}`}>
                  How can I help you today?
                </h1>
              )}
            </div>
          </div>
        ) : (
          <Virtuoso
            ref={virtuosoRef}
            data={displayMessages}
            initialTopMostItemIndex={displayMessages.length - 1}
            startReached={handleStartReached}
            followOutput="smooth"
            itemContent={(index, message) => (
              <MessageBubble
                message={message}
                isStreaming={message.id === 'streaming'}
                streamingText={streamingText}
                isEphemeral={ephemeralMessages.some(em => em.id === message.id)}
                onCopy={() => navigator.clipboard.writeText(message.content)}
                onRegenerate={() => handleRegenerate(message.id)}
                onAddToPlan={() => handleAddToPlan(message.id)}
                onLike={() => {}}
                onDislike={() => {}}
              />
            )}
            style={{ height: '100%' }}
          />
        )}
      </div>

      {/* FAB */}

      {/* Input Area */}
      <div className={`border-t shadow-lg ${isDark ? 'border-gray-700 bg-gray-800' : 'border-gray-200 bg-white'}`}>
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onCompositionStart={() => setIsComposing(true)}
              onCompositionEnd={() => setIsComposing(false)}
              placeholder="Message..."
              className={`w-full px-4 py-3 pr-12 rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm max-h-[200px] overflow-y-auto ${
                isDark 
                  ? 'bg-gray-700 border-2 border-gray-600 text-white placeholder-gray-400' 
                  : 'bg-gray-50 border-2 border-gray-300 text-gray-900 placeholder-gray-500'
              }`}
              rows={1}
            />
            <div className="absolute right-3 bottom-3 flex items-center gap-2">
              <button
                type="button"
                onClick={handleFileUpload}
                className={`p-1.5 rounded-lg transition-colors ${
                  isDark 
                    ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700' 
                    : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                }`}
                title="Attach file (PDF, DOC, TXT)"
                disabled={isUploading}
              >
                <Paperclip size={18} />
              </button>
              <button
                onClick={() => {
                  if (isListening) {
                    stopListening();
                  } else {
                    startListening();
                  }
                }}
                className={`p-1.5 rounded-lg transition-colors relative ${
                  isListening
                    ? `text-red-600 ${isDark ? 'hover:bg-red-900/30' : 'hover:bg-red-50'} animate-pulse`
                    : isDark 
                      ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
                      : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                }`}
                title={isListening ? 'Stop recording' : 'Start voice input'}
              >
                <Mic size={18} />
                {isListening && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 bg-red-600 rounded-full animate-ping"></span>
                )}
              </button>
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="flex-shrink-0 p-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors shadow-md"
                title="Send message"
              >
                <Send size={18} className="text-white" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={handleFileChange}
        accept=".pdf,.doc,.docx,.txt"
      />
    </div>
  );
}
