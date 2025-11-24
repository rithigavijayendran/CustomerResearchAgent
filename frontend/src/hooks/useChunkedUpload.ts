// Chunked upload hook with progress tracking
import { useState, useCallback } from 'react';
import { uploadApi } from '../lib/api';

interface UseChunkedUploadOptions {
  onProgress?: (progress: number) => void;
  onComplete?: (uploadId: string, jobId?: string) => void;
  onError?: (error: string) => void;
  companyName?: string;
  chatId?: string;
}

export function useChunkedUpload({ onProgress, onComplete, onError, companyName, chatId }: UseChunkedUploadOptions = {}) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const uploadFile = useCallback(async (file: File, chunkSize: number = 5 * 1024 * 1024, overrideChatId?: string, overrideCompanyName?: string) => {
    try {
      setUploading(true);
      setProgress(0);

      // Use override values if provided, otherwise use from props
      const currentChatId = overrideChatId || chatId;
      const currentCompanyName = overrideCompanyName || companyName;
      
      // Initialize upload with company name and chat ID
      const session = await uploadApi.initUpload(currentCompanyName, currentChatId);
      const totalChunks = Math.ceil(file.size / chunkSize);

      // Upload chunks
      for (let i = 0; i < totalChunks; i++) {
        const start = i * chunkSize;
        const end = Math.min(start + chunkSize, file.size);
        const chunk = file.slice(start, end);
        
        const chunkFile = new File([chunk], file.name, { type: file.type });
        await uploadApi.uploadChunk(session.uploadId, i, totalChunks, chunkFile);
        
        const currentProgress = ((i + 1) / totalChunks) * 100;
        setProgress(currentProgress);
        onProgress?.(currentProgress);
      }
      
      // Complete upload - pass company name and chat ID
      const result = await uploadApi.completeUpload(session.uploadId, currentCompanyName, currentChatId);
      setUploading(false);
      setProgress(100);
      onComplete?.(session.uploadId, result.jobId);
      
      return { uploadId: session.uploadId, jobId: result.jobId };
    } catch (error: any) {
      setUploading(false);
      setProgress(0);
      const errorMsg = error.response?.data?.detail || error.message || 'Upload failed';
      onError?.(errorMsg);
      throw error;
    }
  }, [onProgress, onComplete, onError, companyName, chatId]);

  return {
    uploading,
    progress,
    uploadFile,
  };
}

