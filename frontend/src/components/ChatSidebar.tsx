// ChatGPT-like Sidebar Component
import { useState, useEffect } from 'react';
import { Plus, Search, MessageSquare, User, LogOut, Trash2 } from 'lucide-react';
import { chatApi } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../hooks/useTheme';
import type { Chat } from '../types';

interface ChatSidebarProps {
  currentChatId: string | null;
  onChatSelect: (chatId: string) => void;
  onNewChat: () => void;
  onLogout?: () => void;
}

export function ChatSidebar({ currentChatId, onChatSelect, onNewChat, onLogout }: ChatSidebarProps) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const { user } = useAuth();
  const { theme } = useTheme();
  
  const isDark = theme === 'dark';

  useEffect(() => {
    loadChats();
    // Reload chats periodically to catch title updates (when account plan is created)
    // Use longer interval to avoid rate limiting
    const interval = setInterval(() => {
      loadChats();
    }, 10000); // Reload every 10 seconds to avoid rate limiting
    
    return () => clearInterval(interval);
  }, []);

  const loadChats = async () => {
    try {
      setIsLoading(true);
      const data = await chatApi.listChats(1, 50);
      setChats(data.chats);
    } catch (error) {
      console.error('Failed to load chats:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteChat = async (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation(); // Prevent chat selection
    if (!window.confirm('Are you sure you want to delete this chat? This action cannot be undone.')) {
      return;
    }
    
    try {
      await chatApi.deleteChat(chatId);
      // Reload chats after deletion
      await loadChats();
      // If deleted chat was selected, clear selection
      if (currentChatId === chatId) {
        onChatSelect('');
      }
    } catch (error) {
      console.error('Failed to delete chat:', error);
      alert('Failed to delete chat. Please try again.');
    }
  };

  const filteredChats = chats.filter(chat =>
    chat.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Removed formatDate - no longer showing dates in chat sidebar

  return (
    <div className={`flex flex-col h-full text-white w-64 border-r shadow-lg ${
      isDark 
        ? 'bg-gradient-to-b from-gray-800 via-gray-850 to-gray-900 border-gray-700' 
        : 'bg-gradient-to-b from-blue-600 via-purple-600 to-pink-600 border-purple-500'
    }`}>
      {/* New Chat Button */}
      <div className={`p-3 border-b ${isDark ? 'border-gray-700' : 'border-white/20'}`}>
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border-2 border-white/30 hover:bg-white/20 hover:border-white/40 transition-colors text-sm font-medium text-white shadow-md"
        >
          <Plus size={16} />
          <span>New chat</span>
        </button>
      </div>

      {/* Search */}
      <div className={`p-3 border-b ${isDark ? 'border-gray-700' : 'border-white/20'}`}>
        <div className="relative">
          <Search size={16} className={`absolute left-3 top-1/2 transform -translate-y-1/2 ${isDark ? 'text-gray-400' : 'text-white/80'}`} />
          <input
            type="text"
            placeholder="Search chats..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={`w-full pl-9 pr-3 py-2 ${isDark ? 'bg-gray-700/50 border-gray-600 text-white placeholder-gray-400 focus:ring-gray-500 focus:border-gray-500' : 'bg-white/20 border-white/30 text-white placeholder-white/70 focus:ring-white/50 focus:border-white/50'} rounded-lg text-sm focus:outline-none focus:ring-2`}
          />
        </div>
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className={`p-4 text-center text-sm ${isDark ? 'text-gray-300' : 'text-white/80'}`}>Loading chats...</div>
        ) : filteredChats.length === 0 ? (
          <div className={`p-4 text-center text-sm ${isDark ? 'text-gray-300' : 'text-white/80'}`}>
            {searchQuery ? 'No chats found' : 'No chats yet'}
          </div>
        ) : (
          <div className="py-2">
            {filteredChats.map((chat) => (
              <div
                key={chat.id}
                className={`group relative w-full px-3 py-2.5 transition-colors rounded-lg mx-2 ${
                  isDark 
                    ? `hover:bg-gray-700/50 ${currentChatId === chat.id ? 'bg-gray-700/70 border-l-4 border-white' : ''}`
                    : `hover:bg-white/20 ${currentChatId === chat.id ? 'bg-white/30 border-l-4 border-white' : ''}`
                }`}
              >
                <button
                  onClick={() => onChatSelect(chat.id)}
                  className="w-full text-left flex items-center gap-3"
                >
                  <MessageSquare size={16} className={`flex-shrink-0 ${isDark ? 'text-gray-300' : 'text-white/90'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white truncate font-medium">{chat.title || 'New Chat'}</div>
                  </div>
                </button>
                <button
                  onClick={(e) => handleDeleteChat(e, chat.id)}
                  className={`absolute right-2 top-1/2 transform -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1.5 rounded transition-opacity ${
                    isDark ? 'hover:bg-red-600/50' : 'hover:bg-red-500/30'
                  }`}
                  title="Delete chat"
                >
                  <Trash2 size={14} className="text-red-200" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* User Section */}
      <div className={`p-3 border-t ${isDark ? 'border-gray-700' : 'border-white/20'}`}>
        <div className={`flex items-center gap-3 px-2 py-2 rounded-lg transition-colors cursor-pointer group ${
          isDark ? 'hover:bg-gray-700/50' : 'hover:bg-white/20'
        }`}>
          <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
            isDark ? 'bg-gray-700 border-gray-600' : 'bg-white/30 border-white/40'
          }`}>
            {user?.avatarUrl ? (
              <img src={user.avatarUrl} alt={user.name} className="w-full h-full rounded-full object-cover" />
            ) : (
              <User size={18} className="text-white" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white truncate">{user?.name || user?.email || 'User'}</div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              className={`opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded ${
                isDark ? 'hover:bg-gray-700' : 'hover:bg-white/20'
              }`}
              title="Logout"
            >
              <LogOut size={14} className="text-white" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

