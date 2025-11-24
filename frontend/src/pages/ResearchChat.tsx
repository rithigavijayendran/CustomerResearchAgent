// ChatGPT-like Research Chat Page
import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ChatSidebar } from '../components/ChatSidebar';
import { ChatWindow } from '../components/ChatWindow';
import { chatApi } from '../lib/api';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../hooks/useTheme';
import { InfinityLogo } from '../components/InfinityLogo';
import { LogOut, Sun, Moon } from 'lucide-react';
import type { Chat } from '../types';

export default function ResearchChat() {
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<Chat[]>([]);
  const { logout, user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  useEffect(() => {
    loadChats();
  }, []);

  const loadChats = async () => {
    try {
      const data = await chatApi.listChats(1, 50);
      setChats(data.chats);
      // Auto-select first chat if available
      if (data.chats.length > 0 && !currentChatId) {
        setCurrentChatId(data.chats[0].id);
      }
    } catch (error) {
      console.error('Failed to load chats:', error);
    }
  };

  const handleNewChat = async () => {
    try {
      const newChat = await chatApi.createChat();
      setCurrentChatId(newChat.id);
      await loadChats();
    } catch (error) {
      console.error('Failed to create new chat:', error);
    }
  };

  const handleChatSelect = (chatId: string) => {
    setCurrentChatId(chatId);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex flex-col h-screen w-full overflow-hidden">
      {/* Navbar - Same as other pages */}
      <nav className={`shadow-sm border-b flex-shrink-0 ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/dashboard" className="flex items-center space-x-2">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isDark ? 'bg-gray-700' : 'bg-gradient-eightfold'}`}>
                  <InfinityLogo size={20} />
                </div>
                <span className={`text-xl font-semibold ${isDark ? 'text-white' : 'bg-gradient-eightfold bg-clip-text text-transparent'}`}>
                  Eightfold AI
                </span>
              </Link>
            </div>

            {/* Desktop Menu */}
            <div className="hidden md:flex items-center space-x-4">
              <Link
                to="/dashboard"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isDark ? 'text-gray-300 hover:text-white hover:bg-gray-700' : 'text-gray-700 hover:text-blue-600'
                }`}
              >
                Dashboard
              </Link>
              <Link
                to="/research"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isDark ? 'text-gray-300 hover:text-white hover:bg-gray-700' : 'text-gray-700 hover:text-blue-600'
                }`}
              >
                Research
              </Link>
              <Link
                to="/plans"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isDark ? 'text-gray-300 hover:text-white hover:bg-gray-700' : 'text-gray-700 hover:text-blue-600'
                }`}
              >
                Account Plans
              </Link>
              <button
                onClick={toggleTheme}
                className={`p-2 rounded-md transition-colors ${
                  isDark ? 'text-gray-300 hover:text-white hover:bg-gray-700' : 'text-gray-700 hover:text-blue-600 hover:bg-gray-100'
                }`}
                title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {isDark ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              <div className="flex items-center space-x-4 pl-4 border-l border-gray-300 dark:border-gray-700">
                <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{user?.name}</span>
                <button
                  onClick={handleLogout}
                  className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isDark ? 'text-gray-300 hover:text-white hover:bg-gray-700' : 'text-gray-700 hover:text-blue-600'
                  }`}
                >
                  <LogOut className="w-4 h-4" />
                  <span>Logout</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Chat Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <div className="flex-shrink-0">
          <ChatSidebar
            currentChatId={currentChatId}
            onChatSelect={handleChatSelect}
            onNewChat={handleNewChat}
            onLogout={handleLogout}
          />
        </div>

        {/* Main Chat Window */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          <ChatWindow
            chatId={currentChatId}
            onNewChat={handleNewChat}
            onChatCreated={(chatId) => {
              setCurrentChatId(chatId);
              loadChats();
            }}
            onPlanUpdated={() => {
              loadChats(); // Reload chats when plan is updated (to show updated chat title)
            }}
          />
        </div>
      </div>
    </div>
  );
}

