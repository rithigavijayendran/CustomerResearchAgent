// PlanViewer component with inline editing, regeneration, version history, PDF download, Add/Remove fields
import { useState, useEffect } from 'react';
import { Edit2, RefreshCw, Download, History, ChevronDown, ChevronUp, Plus, Trash2, ArrowLeft, TrendingUp, Target, AlertTriangle, Zap } from 'lucide-react';
import { planApi } from '../lib/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { useTheme } from '../hooks/useTheme';
import type { AccountPlan, PlanVersion } from '../types';
import ReactMarkdown from 'react-markdown';

interface PlanViewerProps {
  planId: string;
  onReturnToChat?: () => void;
  chatId?: string;
}

interface SectionProps {
  sectionKey: string;
  sectionLabel: string;
  content: string;
  isEditing: boolean;
  onEdit: () => void;
  onSave: (content: string) => void;
  onCancel: () => void;
  onRegenerate: () => void;
  isRegenerating: boolean;
  onDelete?: () => void;
}

function Section({
  sectionKey,
  sectionLabel,
  content,
  isEditing,
  onEdit,
  onSave,
  onCancel,
  onRegenerate,
  isRegenerating,
  onDelete,
}: SectionProps) {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [editContent, setEditContent] = useState(content);
  const [isCollapsed, setIsCollapsed] = useState(false);

  useEffect(() => {
    setEditContent(content);
  }, [content]);

  const handleSave = () => {
    onSave(editContent);
  };

  return (
    <div className={`border rounded-xl mb-6 shadow-sm transition-all hover:shadow-md ${
      isDark ? 'border-gray-700 bg-gray-800/50' : 'border-gray-200 bg-white'
    }`}>
      <div className={`flex items-center justify-between p-5 rounded-t-xl ${
        isDark ? 'bg-gray-800/80' : 'bg-gradient-to-r from-blue-50 to-purple-50'
      }`}>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className={`p-1.5 rounded-lg transition-colors ${
              isDark 
                ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700' 
                : 'text-gray-600 hover:text-gray-800 hover:bg-gray-200'
            }`}
          >
            {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
          </button>
          <h3 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{sectionLabel}</h3>
        </div>
        <div className="flex gap-2">
          {!isEditing ? (
            <>
              <button
                onClick={onEdit}
                className={`p-2.5 rounded-lg transition-all ${
                  isDark 
                    ? 'text-blue-400 hover:bg-blue-900/30 hover:text-blue-300' 
                    : 'text-blue-600 hover:bg-blue-50 hover:text-blue-700'
                }`}
                title="Edit"
              >
                <Edit2 size={18} />
              </button>
              <button
                onClick={onRegenerate}
                disabled={isRegenerating}
                className={`p-2.5 rounded-lg transition-all disabled:opacity-50 ${
                  isDark 
                    ? 'text-green-400 hover:bg-green-900/30 hover:text-green-300' 
                    : 'text-green-600 hover:bg-green-50 hover:text-green-700'
                }`}
                title="Regenerate"
              >
                <RefreshCw size={18} className={isRegenerating ? 'animate-spin' : ''} />
              </button>
              {onDelete && (
                <button
                  onClick={onDelete}
                  className={`p-2.5 rounded-lg transition-all ${
                    isDark 
                      ? 'text-red-400 hover:bg-red-900/30 hover:text-red-300' 
                      : 'text-red-600 hover:bg-red-50 hover:text-red-700'
                  }`}
                  title="Remove Section"
                >
                  <Trash2 size={18} />
                </button>
              )}
            </>
          ) : (
            <>
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 transition-all shadow-md"
              >
                Save
              </button>
              <button
                onClick={onCancel}
                className={`px-4 py-2 rounded-lg transition-all ${
                  isDark 
                    ? 'bg-gray-700 text-gray-200 hover:bg-gray-600' 
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                Cancel
              </button>
            </>
          )}
        </div>
      </div>
      
      {!isCollapsed && (
        <div className="p-6">
          {isEditing ? (
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className={`w-full min-h-[250px] rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all ${
                isDark 
                  ? 'bg-gray-800 border-gray-600 text-white placeholder-gray-400' 
                  : 'bg-gray-50 border-gray-300 text-gray-900 placeholder-gray-500'
              } border`}
            />
          ) : (
            <div className={`prose prose-lg dark:prose-invert max-w-none whitespace-pre-wrap ${
              isDark ? 'text-gray-200' : 'text-gray-700'
            }`}>
              <ReactMarkdown>{content || 'No content available'}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function VersionHistory({ versions, onRevert }: { versions: PlanVersion[]; onRevert: (versionId: string) => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

  const renderDiff = (version: PlanVersion) => {
    if (!version.diff) {
      return (
        <div className="text-sm text-gray-600 dark:text-gray-400">
          <div className="bg-red-50 dark:bg-red-900/20 p-2 rounded mb-2">
            <div className="font-medium mb-1">Removed:</div>
            <div className="line-through text-gray-500">{version.changes.oldContent || 'N/A'}</div>
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 p-2 rounded">
            <div className="font-medium mb-1">Added:</div>
            <div>{version.changes.newContent || 'N/A'}</div>
          </div>
        </div>
      );
    }

    // Render structured diff if available
    return (
      <div className="text-sm space-y-2">
        {Object.entries(version.diff).map(([key, value]) => (
          <div key={key} className="border border-gray-200 dark:border-gray-700 rounded p-2">
            <div className="font-medium text-xs text-gray-500 mb-1">{key}</div>
            <div className="text-gray-700 dark:text-gray-300">{String(value)}</div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg mb-4">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700"
      >
        <div className="flex items-center gap-2">
          <History size={20} />
          <span className="font-semibold">Version History ({versions.length})</span>
        </div>
        {isOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
      </button>
      
      {isOpen && (
        <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
          {versions.map((version) => (
            <div
              key={version.versionId}
              className="border border-gray-200 dark:border-gray-700 rounded p-3"
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex-1">
                  <div className="text-sm font-medium">
                    {new Date(version.timestamp).toLocaleString()}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Section: {version.changes.section} | User: {version.userId}
                  </div>
                </div>
                <button
                  onClick={() => onRevert(version.versionId)}
                  className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 ml-2"
                >
                  Revert
                </button>
              </div>
              {selectedVersion === version.versionId ? (
                <div className="mt-2">
                  {renderDiff(version)}
                  <button
                    onClick={() => setSelectedVersion(null)}
                    className="mt-2 text-xs text-blue-600 hover:underline"
                  >
                    Hide diff
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setSelectedVersion(version.versionId)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Show diff
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function PlanViewer({ planId, onReturnToChat, chatId }: PlanViewerProps) {
  const [plan, setPlan] = useState<AccountPlan | null>(null);
  const [editingSection, setEditingSection] = useState<string | null>(null);
  const [regeneratingSection, setRegeneratingSection] = useState<string | null>(null);
  const [regeneratingContent, setRegeneratingContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [newFieldName, setNewFieldName] = useState('');
  const [editContent, setEditContent] = useState<string>('');

  // All hooks must be called before any conditional returns
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  // WebSocket for streaming (not used for regeneration, but kept for potential future use)
  useWebSocket({
    chatId: chatId || '',
    onToken: () => {},
    onProgress: () => {},
    onComplete: () => {},
    onError: () => {},
  });

  useEffect(() => {
    loadPlan();
  }, [planId]);

  const loadPlan = async () => {
    try {
      setLoading(true);
      const data = await planApi.getPlan(planId);
      setPlan(data);
    } catch (error) {
      console.error('Failed to load plan:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSection = async (sectionKey: string, content: string) => {
    try {
      await planApi.updateSection(planId, sectionKey, content);
      await loadPlan();
      setEditingSection(null);
      setEditContent('');
    } catch (error) {
      console.error('Failed to save section:', error);
    }
  };

  const handleRegenerateSection = async (sectionKey: string) => {
    try {
      setRegeneratingSection(sectionKey);
      setRegeneratingContent('');
      
      // Call the regenerate API endpoint which returns the content directly
      // The backend already saves the regenerated content to the database
      const response = await planApi.regenerateSection(planId, sectionKey);
      
      // Show the regenerated content while loading
      if (response && response.content) {
        setRegeneratingContent(response.content);
      }
      
      // Reload the plan to get the updated content from the database
      await loadPlan();
      
      setRegeneratingSection(null);
      setRegeneratingContent('');
    } catch (error: any) {
      console.error('Failed to regenerate section:', error);
      setRegeneratingSection(null);
      setRegeneratingContent('');
      
      // Show user-friendly error message
      const errorMessage = error?.response?.data?.detail || error?.message || 'Failed to regenerate section. Please try again.';
      alert(errorMessage);
    }
  };

  const handleAddField = async () => {
    if (!newFieldName.trim() || !plan) return;
    
    const fieldKey = newFieldName.toLowerCase().replace(/\s+/g, '_');
    
    try {
      // Update plan with new field
      await planApi.updateSection(planId, fieldKey, '');
      setNewFieldName('');
      await loadPlan();
    } catch (error) {
      console.error('Failed to add field:', error);
    }
  };

  const handleRemoveField = async (sectionKey: string) => {
    if (!plan) return;
    
    if (confirm(`Remove section "${sectionKey}"?`)) {
      try {
        // Set field to empty (or remove from plan)
        await planApi.updateSection(planId, sectionKey, '');
        await loadPlan();
      } catch (error) {
        console.error('Failed to remove field:', error);
      }
    }
  };

  const handleRevertVersion = async (versionId: string) => {
    if (!plan) return;
    
    const version = plan.versions.find(v => v.versionId === versionId);
    if (!version) return;
    
    try {
      const sectionKey = version.changes.section;
      const content = version.changes.oldContent || '';
      await planApi.updateSection(planId, sectionKey, content);
      await loadPlan();
    } catch (error) {
      console.error('Failed to revert version:', error);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      const blob = await planApi.downloadPDF(planId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${plan?.companyName || 'AccountPlan'}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download PDF:', error);
    }
  };

  const handleReturnToChat = () => {
    if (onReturnToChat) {
      // Store section info for highlighting if chatId is available
      if (chatId) {
        sessionStorage.setItem('highlightSection', JSON.stringify({
          chatId,
          timestamp: Date.now()
        }));
      }
      onReturnToChat();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-600">Loading plan...</div>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-600">Plan not found</div>
      </div>
    );
  }

  const sectionLabels: { [key: string]: string } = {
    company_name: 'Company Name',
    company_overview: 'Company Overview',
    market_summary: 'Market Summary',
    key_insights: 'Key Insights',
    pain_points: 'Pain Points',
    opportunities: 'Opportunities',
    competitor_analysis: 'Competitor Analysis',
    swot: 'SWOT Analysis',
    strategic_recommendations: 'Strategic Recommendations',
    final_account_plan: 'Executive Summary',
    products_services: 'Products & Services',
    recommended_strategy: 'Recommended Strategy',
  };

  // Helper function to render SWOT analysis with beautiful grid layout
  const renderSWOT = (swotData: any) => {
    if (!swotData || typeof swotData !== 'object') return null;
    
    const swotItems = [
      { key: 'strengths', label: 'Strengths', icon: TrendingUp, color: 'green', bgColor: isDark ? 'bg-green-900/20' : 'bg-green-50', borderColor: isDark ? 'border-green-800' : 'border-green-200', textColor: isDark ? 'text-green-300' : 'text-green-700', iconBg: isDark ? 'bg-green-900/30' : 'bg-green-100' },
      { key: 'weaknesses', label: 'Weaknesses', icon: AlertTriangle, color: 'yellow', bgColor: isDark ? 'bg-yellow-900/20' : 'bg-yellow-50', borderColor: isDark ? 'border-yellow-800' : 'border-yellow-200', textColor: isDark ? 'text-yellow-300' : 'text-yellow-700', iconBg: isDark ? 'bg-yellow-900/30' : 'bg-yellow-100' },
      { key: 'opportunities', label: 'Opportunities', icon: Target, color: 'blue', bgColor: isDark ? 'bg-blue-900/20' : 'bg-blue-50', borderColor: isDark ? 'border-blue-800' : 'border-blue-200', textColor: isDark ? 'text-blue-300' : 'text-blue-700', iconBg: isDark ? 'bg-blue-900/30' : 'bg-blue-100' },
      { key: 'threats', label: 'Threats', icon: Zap, color: 'red', bgColor: isDark ? 'bg-red-900/20' : 'bg-red-50', borderColor: isDark ? 'border-red-800' : 'border-red-200', textColor: isDark ? 'text-red-300' : 'text-red-700', iconBg: isDark ? 'bg-red-900/30' : 'bg-red-100' },
    ];

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {swotItems.map(({ key, label, icon: Icon, bgColor, borderColor, textColor, iconBg }) => {
          const value = swotData[key] || '';
          const isEditing = editingSection === `swot.${key}`;
          
          return (
            <div key={key} className={`border-2 rounded-xl p-6 ${bgColor} ${borderColor} transition-all hover:shadow-lg`}>
              <div className="flex items-center gap-3 mb-4">
                <div className={`p-2.5 rounded-lg ${iconBg}`}>
                  <Icon size={24} className={textColor} />
                </div>
                <h4 className={`text-xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{label}</h4>
              </div>
              {isEditing ? (
                <div className="space-y-3">
                  <textarea
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className={`w-full min-h-[150px] rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all ${
                      isDark 
                        ? 'bg-gray-800 border-gray-600 text-white' 
                        : 'bg-white border-gray-300 text-gray-900'
                    } border`}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleSaveSection(`swot.${key}`, editContent)}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => {
                        setEditingSection(null);
                        setEditContent('');
                      }}
                      className={`px-4 py-2 rounded-lg transition-colors ${
                        isDark ? 'bg-gray-700 text-gray-200 hover:bg-gray-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className={`prose prose-sm dark:prose-invert max-w-none ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                    <ReactMarkdown>{value || `No ${label.toLowerCase()} identified yet.`}</ReactMarkdown>
                  </div>
                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={() => {
                        setEditContent(value);
                        setEditingSection(`swot.${key}`);
                      }}
                      className={`p-2 rounded-lg transition-all ${
                        isDark 
                          ? 'text-blue-400 hover:bg-blue-900/30' 
                          : 'text-blue-600 hover:bg-blue-50'
                      }`}
                      title="Edit"
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      onClick={() => handleRegenerateSection(`swot.${key}`)}
                      disabled={regeneratingSection === `swot.${key}`}
                      className={`p-2 rounded-lg transition-all disabled:opacity-50 ${
                        isDark 
                          ? 'text-green-400 hover:bg-green-900/30' 
                          : 'text-green-600 hover:bg-green-50'
                      }`}
                      title="Regenerate"
                    >
                      <RefreshCw size={16} className={regeneratingSection === `swot.${key}` ? 'animate-spin' : ''} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  // Define the desired section order (Company Name at top, SWOT in the middle)
  const sectionOrder = [
    'company_name', // Company Name at the very top
    'company_overview',
    'market_summary',
    'key_insights',
    'pain_points',
    'opportunities',
    'competitor_analysis',
    'swot', // SWOT in the middle
    'strategic_recommendations',
    'final_account_plan',
    'products_services',
    'recommended_strategy'
  ];

  // Separate flat sections and nested structures
  const flatSections = Object.entries(plan.planJSON || {})
    .filter(([key, value]) => {
      // Skip nested objects (like SWOT) and empty values
      if (key === 'swot') return false; // Handle SWOT separately
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        return false; // Skip nested objects
      }
      return typeof value === 'string' && value.trim() !== '';
    });

  const swotData = plan.planJSON?.swot;

  // Organize sections in the desired order
  const orderedSections: Array<{ key: string; content: string; type: 'regular' | 'swot' }> = [];
  
  // Add sections in order
  sectionOrder.forEach((key) => {
    if (key === 'swot') {
      // Add SWOT if it exists
      if (swotData && typeof swotData === 'object') {
        orderedSections.push({ key: 'swot', content: '', type: 'swot' });
      }
    } else {
      // Add regular section if it exists
      const section = flatSections.find(([k]) => k === key);
      if (section) {
        orderedSections.push({ key: section[0], content: section[1] as string, type: 'regular' });
      }
    }
  });

  // Add any remaining sections that weren't in the order list
  flatSections.forEach(([key, content]) => {
    if (!sectionOrder.includes(key)) {
      orderedSections.push({ key, content: content as string, type: 'regular' });
    }
  });

  return (
    <div className={`h-full overflow-y-auto ${isDark ? 'bg-gray-900' : 'bg-gray-50'}`}>
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className={`flex items-center justify-between mb-8 p-6 rounded-2xl shadow-lg ${
          isDark ? 'bg-gradient-to-r from-gray-800 to-gray-700' : 'bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600'
        }`}>
          <div>
            <h1 className={`text-4xl font-bold mb-2 ${isDark ? 'text-white' : 'text-white'}`}>
              {plan.companyName} - Account Plan
            </h1>
            <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-white/90'}`}>
              Last updated: {new Date(plan.updatedAt).toLocaleString()}
            </p>
          </div>
          <div className="flex gap-3">
            {onReturnToChat && (
              <button
                onClick={handleReturnToChat}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-lg transition-all shadow-md ${
                  isDark 
                    ? 'bg-gray-700 text-gray-200 hover:bg-gray-600' 
                    : 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-sm'
                }`}
              >
                <ArrowLeft size={18} />
                Return to Chat
              </button>
            )}
            <button
              onClick={handleDownloadPDF}
              className="flex items-center gap-2 px-5 py-2.5 bg-white text-blue-600 rounded-lg hover:bg-blue-50 transition-all shadow-md font-semibold"
            >
              <Download size={18} />
              Download PDF
            </button>
          </div>
        </div>

        {/* Version History */}
        {plan.versions && plan.versions.length > 0 && (
          <VersionHistory versions={plan.versions} onRevert={handleRevertVersion} />
        )}

        {/* Sections in Order (SWOT in the middle) */}
        {orderedSections.map(({ key, content, type }) => {
          if (type === 'swot' && swotData && typeof swotData === 'object') {
            return (
              <div key="swot" className={`mb-8 rounded-2xl p-6 shadow-lg ${
                isDark ? 'bg-gray-800 border border-gray-700' : 'bg-white border border-gray-200'
              }`}>
                <div className="flex items-center justify-between mb-6">
                  <h2 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>
                    SWOT Analysis
                  </h2>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleRegenerateSection('swot')}
                      disabled={regeneratingSection === 'swot'}
                      className={`p-2.5 rounded-lg transition-all disabled:opacity-50 ${
                        isDark 
                          ? 'text-green-400 hover:bg-green-900/30' 
                          : 'text-green-600 hover:bg-green-50'
                      }`}
                      title="Regenerate SWOT"
                    >
                      <RefreshCw size={18} className={regeneratingSection === 'swot' ? 'animate-spin' : ''} />
                    </button>
                  </div>
                </div>
                {renderSWOT(swotData)}
              </div>
            );
          } else {
            return (
              <Section
                key={key}
                sectionKey={key}
                sectionLabel={sectionLabels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                content={content}
                isEditing={editingSection === key}
                onEdit={() => {
                  setEditContent(content);
                  setEditingSection(key);
                }}
                onSave={(newContent) => handleSaveSection(key, newContent)}
                onCancel={() => setEditingSection(null)}
                onRegenerate={() => handleRegenerateSection(key)}
                isRegenerating={regeneratingSection === key}
                onDelete={() => handleRemoveField(key)}
              />
            );
          }
        })}

        {/* Add Field */}
        <div className={`border-2 border-dashed rounded-xl p-6 mb-6 transition-all hover:border-solid ${
          isDark 
            ? 'border-gray-700 bg-gray-800/50 hover:border-gray-600' 
            : 'border-gray-300 bg-white hover:border-blue-400'
        }`}>
          <div className="flex items-center gap-3 mb-4">
            <div className={`p-2 rounded-lg ${isDark ? 'bg-blue-900/30' : 'bg-blue-100'}`}>
              <Plus size={20} className={isDark ? 'text-blue-400' : 'text-blue-600'} />
            </div>
            <span className={`text-lg font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>Add New Field</span>
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={newFieldName}
              onChange={(e) => setNewFieldName(e.target.value)}
              placeholder="Field name (e.g., Market Trends, Financial Overview)"
              className={`flex-1 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all ${
                isDark 
                  ? 'bg-gray-800 border-gray-600 text-white placeholder-gray-400' 
                  : 'bg-gray-50 border-gray-300 text-gray-900 placeholder-gray-500'
              } border`}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleAddField();
                }
              }}
            />
            <button
              onClick={handleAddField}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 transition-all shadow-md font-semibold"
            >
              Add Field
            </button>
          </div>
        </div>

        {/* Regenerating indicator */}
        {regeneratingSection && (
          <div className="fixed bottom-6 right-6 bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-4 rounded-xl shadow-2xl z-50 border-2 border-white/20">
            <div className="flex items-center gap-3">
              <RefreshCw size={20} className="animate-spin" />
              <div>
                <div className="font-semibold">
                  Regenerating {sectionLabels[regeneratingSection] || regeneratingSection.replace('swot.', '').replace(/_/g, ' ')}...
                </div>
                {regeneratingContent && (
                  <div className="mt-2 text-sm opacity-90 max-w-md">
                    {regeneratingContent.substring(0, 100)}...
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
