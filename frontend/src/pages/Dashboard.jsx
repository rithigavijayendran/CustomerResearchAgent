import { Link } from 'react-router-dom'
import { Search, FileText, History, Sparkles, ArrowRight, TrendingUp, Zap } from 'lucide-react'
import { useTheme } from '../hooks/useTheme'

export default function Dashboard() {
  const { theme } = useTheme()
  const isDark = theme === 'dark'

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
        {/* Hero Section */}
        <div className="mb-12 text-center">
          <h1 className="text-5xl font-bold mb-4 text-white">
            Welcome to Your Dashboard
          </h1>
          <p className="text-xl text-white/90">
            Start researching companies and generating comprehensive account plans
          </p>
        </div>

        {/* Feature Cards */}
        <div className="grid md:grid-cols-3 gap-6 mb-12">
          {/* Start Research Card */}
          <Link
            to="/research"
            className="group relative bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 text-white rounded-2xl p-8 hover:shadow-2xl hover:scale-105 transition-all duration-300 overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-blue-700/50 to-purple-700/50 opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-6">
                <div className="w-16 h-16 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                  <Search className="w-8 h-8" />
                </div>
                <Sparkles className="w-6 h-6 opacity-80 animate-pulse" />
              </div>
              <h3 className="text-2xl font-bold mb-3">Start Company Research</h3>
              <p className="text-blue-100 mb-4">
                Begin researching a company with AI-powered analysis and comprehensive insights
              </p>
              <div className="flex items-center text-white/80 group-hover:text-white transition-colors">
                <span className="font-semibold">Get Started</span>
                <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>

          {/* Account Plans Card */}
          <Link
            to="/plans"
            className={`group relative ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-2 rounded-2xl p-8 hover:border-blue-500 hover:shadow-2xl hover:scale-105 transition-all duration-300`}
          >
            <div className="flex items-center justify-between mb-6">
              <div className={`w-16 h-16 ${isDark ? 'bg-blue-900/30' : 'bg-blue-100'} rounded-xl flex items-center justify-center`}>
                <FileText className={`w-8 h-8 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
              </div>
              <TrendingUp className={`w-6 h-6 ${isDark ? 'text-blue-400' : 'text-blue-600'} opacity-60 group-hover:opacity-100 transition-opacity`} />
            </div>
            <h3 className={`text-2xl font-bold mb-3 ${isDark ? 'text-white' : 'text-gray-900'}`}>Saved Account Plans</h3>
            <p className={`mb-4 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              View, edit, and manage your saved account plans with ease
            </p>
            <div className={`flex items-center ${isDark ? 'text-blue-400' : 'text-blue-600'} group-hover:${isDark ? 'text-blue-300' : 'text-blue-700'} transition-colors`}>
              <span className="font-semibold">View Plans</span>
              <ArrowRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
            </div>
          </Link>

          {/* Research History Card */}
          <div className={`group relative ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-2 rounded-2xl p-8 hover:border-purple-500 hover:shadow-2xl transition-all duration-300`}>
            <div className="flex items-center justify-between mb-6">
              <div className={`w-16 h-16 ${isDark ? 'bg-purple-900/30' : 'bg-purple-100'} rounded-xl flex items-center justify-center`}>
                <History className={`w-8 h-8 ${isDark ? 'text-purple-400' : 'text-purple-600'}`} />
              </div>
              <Zap className={`w-6 h-6 ${isDark ? 'text-purple-400' : 'text-purple-600'} opacity-60`} />
            </div>
            <h3 className={`text-2xl font-bold mb-3 ${isDark ? 'text-white' : 'text-gray-900'}`}>Research History</h3>
            <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>
              View your past research sessions, insights, and analysis logs
            </p>
          </div>
        </div>

        {/* Quick Start Guide */}
        <div className={`${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} rounded-2xl p-8 border-2 shadow-lg`}>
          <div className="flex items-center mb-6">
            <div className={`w-12 h-12 ${isDark ? 'bg-gradient-to-br from-blue-600 to-purple-600' : 'bg-gradient-to-br from-blue-500 to-purple-500'} rounded-xl flex items-center justify-center mr-4`}>
              <Zap className="w-6 h-6 text-white" />
            </div>
            <h2 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>Quick Start Guide</h2>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              { step: 1, title: 'Start Research', desc: 'Click "Start Company Research" to begin your analysis' },
              { step: 2, title: 'Enter Company', desc: 'Enter a company name or upload relevant documents' },
              { step: 3, title: 'AI Analysis', desc: 'Let the AI agent research and generate comprehensive insights' },
              { step: 4, title: 'Review & Edit', desc: 'Review and edit the generated plan sections as needed' },
              { step: 5, title: 'Save Plan', desc: 'Save your account plan for future reference and updates' },
            ].map((item) => (
              <div key={item.step} className={`flex items-start p-4 rounded-xl ${isDark ? 'bg-gray-700/50' : 'bg-gray-50'} hover:${isDark ? 'bg-gray-700' : 'bg-gray-100'} transition-colors`}>
                <div className={`w-8 h-8 ${isDark ? 'bg-blue-600' : 'bg-blue-500'} text-white rounded-lg flex items-center justify-center font-bold mr-4 flex-shrink-0`}>
                  {item.step}
                </div>
                <div>
                  <h3 className={`font-semibold mb-1 ${isDark ? 'text-white' : 'text-gray-900'}`}>{item.title}</h3>
                  <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

