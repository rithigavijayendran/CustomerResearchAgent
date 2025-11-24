// Profile page with blue and white theme - perfect UI for editing name, password, and photo
import { useState, useEffect } from 'react';
import { Upload, Save, User as UserIcon, Mail, Lock, Camera } from 'lucide-react';
import { authApi } from '../lib/api';
import type { User } from '../types';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function Profile() {
  const [user, setUser] = useState<User | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await authApi.getProfile();
      setUser(data);
      setName(data.name || '');
      setEmail(data.email || '');
      if (data.avatarUrl) {
        setAvatarPreview(data.avatarUrl.startsWith('http') ? data.avatarUrl : `${API_URL}${data.avatarUrl}`);
      }
    } catch (error) {
      console.error('Failed to load profile:', error);
      setMessage({ type: 'error', text: 'Failed to load profile' });
    } finally {
      setLoading(false);
    }
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setMessage({ type: 'error', text: 'Avatar must be less than 5MB' });
        return;
      }
      
      if (!file.type.startsWith('image/')) {
        setMessage({ type: 'error', text: 'File must be an image' });
        return;
      }
      
      setAvatarFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
      
      // Upload immediately
      await uploadAvatar(file);
    }
  };

  const uploadAvatar = async (file: File) => {
    try {
      setUploadingAvatar(true);
      const token = localStorage.getItem('token');
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post(`${API_URL}/api/auth/profile/avatar`, formData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      });
      
      if (response.data.avatarUrl) {
        const avatarUrl = response.data.avatarUrl.startsWith('http') 
          ? response.data.avatarUrl 
          : `${API_URL}${response.data.avatarUrl}`;
        setAvatarPreview(avatarUrl);
        setMessage({ type: 'success', text: 'Avatar uploaded successfully' });
        // Reload profile to get updated data
        await loadProfile();
      }
    } catch (error: any) {
      console.error('Failed to upload avatar:', error);
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to upload avatar',
      });
    } finally {
      setUploadingAvatar(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage(null);

      // Validate password change
      if (newPassword) {
        if (newPassword.length < 6) {
          setMessage({ type: 'error', text: 'Password must be at least 6 characters' });
          setSaving(false);
          return;
        }
        if (newPassword !== confirmPassword) {
          setMessage({ type: 'error', text: 'Passwords do not match' });
          setSaving(false);
          return;
        }
        if (!oldPassword) {
          setMessage({ type: 'error', text: 'Please enter your current password' });
          setSaving(false);
          return;
        }
      }

      // Update profile
      const updateData: any = {
        name,
        email,
      };

      if (newPassword) {
        updateData.oldPassword = oldPassword;
        updateData.newPassword = newPassword;
      }

      if (avatarPreview && avatarPreview.startsWith('data:')) {
        // If avatar was changed but not uploaded yet, upload it first
        if (avatarFile) {
          await uploadAvatar(avatarFile);
        }
      }

      const updated = await authApi.updateProfile(updateData);
      setUser(updated);
      setMessage({ type: 'success', text: 'Profile updated successfully' });
      
      // Clear password fields
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setAvatarFile(null);
    } catch (error: any) {
      console.error('Failed to save profile:', error);
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to update profile',
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600">
        <div className="text-white text-lg">Loading profile...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 relative overflow-hidden py-8 px-4">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-20 left-10 w-72 h-72 bg-blue-400/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-pink-400/20 rounded-full blur-3xl animate-pulse delay-2000"></div>
      </div>
      <div className="relative z-10 max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Profile Settings</h1>
          <p className="text-white/90">Manage your account information and preferences</p>
        </div>

        {/* Message */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-lg border ${
              message.type === 'success'
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-red-50 border-red-200 text-red-800'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Avatar Section */}
        <div className="bg-white rounded-xl shadow-lg border border-blue-100 p-8 mb-6">
          <h2 className="text-2xl font-semibold text-blue-900 mb-6 flex items-center gap-2">
            <Camera className="w-6 h-6" />
            Profile Photo
          </h2>
          <div className="flex items-center gap-8">
            <div className="relative">
              <div className="w-32 h-32 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center overflow-hidden border-4 border-white shadow-lg">
                {avatarPreview ? (
                  <img
                    src={avatarPreview}
                    alt="Avatar"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <UserIcon className="w-16 h-16 text-white" />
                )}
              </div>
              {uploadingAvatar && (
                <div className="absolute inset-0 bg-blue-600 bg-opacity-50 rounded-full flex items-center justify-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
                </div>
              )}
            </div>
            <div className="flex-1">
              <label className="cursor-pointer">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarChange}
                  className="hidden"
                  disabled={uploadingAvatar}
                />
                <div className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors shadow-md">
                  <Upload size={20} />
                  {uploadingAvatar ? 'Uploading...' : 'Upload Photo'}
                </div>
              </label>
              <p className="text-sm text-gray-500 mt-3">
                JPG, PNG or GIF. Max size 5MB. Recommended: 400x400px
              </p>
            </div>
          </div>
        </div>

        {/* Profile Information */}
        <div className="bg-white rounded-xl shadow-lg border border-blue-100 p-8 mb-6">
          <h2 className="text-2xl font-semibold text-blue-900 mb-6 flex items-center gap-2">
            <UserIcon className="w-6 h-6" />
            Personal Information
          </h2>
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-semibold text-blue-900 mb-2 flex items-center gap-2">
                <UserIcon size={16} />
                Full Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border-2 border-blue-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-all"
                placeholder="Enter your full name"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-blue-900 mb-2 flex items-center gap-2">
                <Mail size={16} />
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border-2 border-blue-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-all"
                placeholder="Enter your email address"
              />
            </div>
          </div>
        </div>

        {/* Password Change */}
        <div className="bg-white rounded-xl shadow-lg border border-blue-100 p-8 mb-6">
          <h2 className="text-2xl font-semibold text-blue-900 mb-6 flex items-center gap-2">
            <Lock className="w-6 h-6" />
            Change Password
          </h2>
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-semibold text-blue-900 mb-2">
                Current Password
              </label>
              <input
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                className="w-full border-2 border-blue-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-all"
                placeholder="Enter your current password"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-blue-900 mb-2">
                New Password
              </label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full border-2 border-blue-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-all"
                placeholder="Enter your new password (min 6 characters)"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-blue-900 mb-2">
                Confirm New Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full border-2 border-blue-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 placeholder-gray-400 transition-all"
                placeholder="Confirm your new password"
              />
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg transition-all transform hover:scale-105"
          >
            <Save size={20} />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
