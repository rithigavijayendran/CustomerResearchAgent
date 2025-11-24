// Theme hook for light/dark mode
import { useState, useEffect, useCallback } from 'react';
import { authApi } from '../lib/api';

type Theme = 'light' | 'dark';

const applyTheme = (newTheme: Theme) => {
  const root = document.documentElement;
  
  if (newTheme === 'dark') {
    root.classList.add('dark');
    root.style.setProperty('--bg-primary', '#0b1a2b');
    root.style.setProperty('--bg-secondary', '#0f2537');
    root.style.setProperty('--text-primary', '#ffffff');
    root.style.setProperty('--text-secondary', '#a0aec0');
    root.style.setProperty('--accent', '#00bcd4');
  } else {
    root.classList.remove('dark');
    root.style.setProperty('--bg-primary', '#ffffff');
    root.style.setProperty('--bg-secondary', '#f7fafc');
    root.style.setProperty('--text-primary', '#1a202c');
    root.style.setProperty('--text-secondary', '#4a5568');
    root.style.setProperty('--accent', '#0f6fff');
  }
};

// Cache for profile data to avoid excessive API calls
let profileCache: { data: any; timestamp: number } | null = null;
const PROFILE_CACHE_DURATION = 60000; // 1 minute cache

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    // Initialize from localStorage immediately to avoid flash
    const savedTheme = localStorage.getItem('theme') as Theme;
    if (savedTheme) {
      applyTheme(savedTheme);
      return savedTheme;
    }
    return 'light';
  });

  useEffect(() => {
    // Load theme from user settings or localStorage
    const loadTheme = async () => {
      // Check cache first
      const now = Date.now();
      if (profileCache && (now - profileCache.timestamp) < PROFILE_CACHE_DURATION) {
        const user = profileCache.data;
        if (user.settings?.theme) {
          setTheme(user.settings.theme);
          applyTheme(user.settings.theme);
          return;
        }
      }

      // Check localStorage first to avoid unnecessary API call
      const savedTheme = localStorage.getItem('theme') as Theme;
      if (savedTheme) {
        setTheme(savedTheme);
        applyTheme(savedTheme);
      }

      // Only fetch profile if we don't have a cached theme preference
      try {
        const user = await authApi.getProfile();
        // Update cache
        profileCache = { data: user, timestamp: now };
        
        if (user.settings?.theme) {
          setTheme(user.settings.theme);
          applyTheme(user.settings.theme);
          localStorage.setItem('theme', user.settings.theme);
        }
      } catch {
        // If API fails, use localStorage theme (already set above)
        // This prevents rate limit errors from breaking the theme
      }
    };
    
    loadTheme();
  }, []);

  const toggleTheme = useCallback(async () => {
    const newTheme: Theme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Save to user settings
    try {
      await authApi.updateProfile({
        settings: { theme: newTheme },
      });
    } catch (error) {
      console.error('Failed to save theme preference:', error);
    }
  }, [theme]);

  return { theme, toggleTheme };
}

