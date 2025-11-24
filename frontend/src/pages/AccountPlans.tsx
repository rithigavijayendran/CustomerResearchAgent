// Account Plans Page - Display all account plans
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Edit, Plus, ArrowRight, Trash2 } from 'lucide-react';
import { planApi } from '../lib/api';
import { PlanViewer } from '../components/PlanViewer';
import { useTheme } from '../hooks/useTheme';
import type { AccountPlan } from '../types';

export default function AccountPlans() {
  const [plans, setPlans] = useState<AccountPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  useEffect(() => {
    loadPlans();
  }, []);

  const loadPlans = async () => {
    try {
      setLoading(true);
      // Use the planApi from lib/api.ts which handles auth automatically
      const response = await planApi.listPlans();
      const plansList = response.plans || [];
      
      // Convert to AccountPlan format
      const formattedPlans: AccountPlan[] = plansList
        .filter((plan: any) => {
          // Filter out plans with empty company names or invalid data
          const hasCompanyName = plan.company_name && plan.company_name.trim() !== '';
          const hasPlanData = plan.plan_json && Object.keys(plan.plan_json).length > 0;
          return hasCompanyName && hasPlanData;
        })
        .map((plan: any) => {
          return {
            id: plan.id || plan.planId,
            userId: '',
            chatId: '',
            companyName: plan.company_name || 'Unknown Company',
            planJSON: plan.plan_json || {},  // Use plan_json from API
            versions: [],
            sources: [],
            status: 'draft',
            createdAt: plan.created_at || new Date().toISOString(),
            updatedAt: plan.updated_at || new Date().toISOString(),
          };
        });
      
      setPlans(formattedPlans);
    } catch (error: any) {
      if (error.response?.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleViewPlan = async (planId: string) => {
    // Use the new /api/plans/{planId} endpoint which uses PlanViewer
    setSelectedPlanId(planId);
  };

  const handleBack = () => {
    setSelectedPlanId(null);
    loadPlans(); // Refresh list when going back
  };

  const handleDeletePlan = async (e: React.MouseEvent, planId: string) => {
    e.stopPropagation(); // Prevent plan selection
    if (!window.confirm('Are you sure you want to delete this account plan? This action cannot be undone.')) {
      return;
    }
    
    try {
      await planApi.deletePlan(planId);
      // Reload plans after deletion
      await loadPlans();
      // If deleted plan was selected, clear selection
      if (selectedPlanId === planId) {
        setSelectedPlanId(null);
      }
    } catch (error) {
      console.error('Failed to delete plan:', error);
      alert('Failed to delete account plan. Please try again.');
    }
  };

  // Refresh plans when window regains focus (in case plan was created in another tab)
  useEffect(() => {
    const handleFocus = () => {
      loadPlans();
    };
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-white">Loading account plans...</p>
        </div>
      </div>
    );
  }

  if (selectedPlanId) {
    return (
      <PlanViewer
        planId={selectedPlanId}
        onReturnToChat={handleBack}
      />
    );
  }

  return (
    <div className={`h-full w-full overflow-y-auto relative ${
      isDark 
        ? 'bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900' 
        : 'bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600'
    }`}>
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className={`absolute top-20 left-10 w-72 h-72 rounded-full blur-3xl animate-pulse ${
          isDark ? 'bg-blue-500/10' : 'bg-blue-400/20'
        }`}></div>
        <div className={`absolute bottom-20 right-10 w-96 h-96 rounded-full blur-3xl animate-pulse delay-1000 ${
          isDark ? 'bg-purple-500/10' : 'bg-purple-400/20'
        }`}></div>
        <div className={`absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 rounded-full blur-3xl animate-pulse delay-2000 ${
          isDark ? 'bg-pink-500/10' : 'bg-pink-400/20'
        }`}></div>
      </div>
      <div className="relative z-10 max-w-7xl mx-auto w-full min-h-full p-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Account Plans</h1>
            <p className="text-white/90 text-lg">View and edit your saved account plans</p>
          </div>
          <button
            onClick={() => navigate('/research')}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors flex items-center space-x-2 shadow-lg"
          >
            <Plus className="w-5 h-5" />
            <span>New Research</span>
          </button>
        </div>

        {/* Plans Grid */}
        {plans.length === 0 ? (
          <div className={`${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-blue-200'} rounded-lg border-2 border-dashed p-12 text-center`}>
            <FileText className={`w-20 h-20 mx-auto mb-4 ${isDark ? 'text-blue-400' : 'text-blue-300'}`} />
            <h3 className={`text-2xl font-semibold mb-2 ${isDark ? 'text-white' : 'text-gray-900'}`}>No Account Plans Yet</h3>
            <p className={`mb-6 text-lg ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              Start researching a company to generate your first account plan
            </p>
            <button
              onClick={() => navigate('/research')}
              className="bg-blue-600 text-white px-8 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors inline-flex items-center space-x-2"
            >
              <Plus className="w-5 h-5" />
              <span>Start Research</span>
            </button>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-blue-200'} rounded-xl border p-6 hover:shadow-xl transition-all ${isDark ? 'hover:border-gray-600' : 'hover:border-blue-400'} cursor-pointer`}
                onClick={() => handleViewPlan(plan.id)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className={`text-xl font-bold mb-2 ${isDark ? 'text-white' : 'text-blue-900'}`}>{plan.companyName}</h3>
                    <p className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                      {plan.updatedAt 
                        ? `Updated ${new Date(plan.updatedAt).toLocaleDateString('en-US', { 
                            month: 'short', 
                            day: 'numeric',
                            year: 'numeric'
                          })}`
                        : 'No update date'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`${isDark ? 'bg-blue-900/30' : 'bg-blue-100'} rounded-full p-3`}>
                      <FileText className={`w-6 h-6 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                    </div>
                    <button
                      onClick={(e) => handleDeletePlan(e, plan.id)}
                      className={`p-2 rounded-lg transition-colors group ${isDark ? 'hover:bg-red-900/30' : 'hover:bg-red-100'}`}
                      title="Delete account plan"
                    >
                      <Trash2 size={18} className={`${isDark ? 'text-red-400 group-hover:text-red-300' : 'text-red-500 group-hover:text-red-700'}`} />
                    </button>
                  </div>
                </div>
                
                <div className={`mt-4 pt-4 border-t ${isDark ? 'border-gray-700' : 'border-blue-100'}`}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleViewPlan(plan.id);
                    }}
                    className="w-full bg-blue-600 text-white px-4 py-2.5 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center justify-center space-x-2"
                  >
                    <Edit className="w-4 h-4" />
                    <span>View & Edit</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

