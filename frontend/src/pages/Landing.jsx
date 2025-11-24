import { Link } from 'react-router-dom'
import { ArrowRight, Sparkles, Search, FileText, MessageSquare, Zap, TrendingUp, Shield } from 'lucide-react'
import { HorizontalLogo } from '../components/HorizontalLogo'

export default function Landing() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 relative overflow-hidden">
      {/* Animated Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-20 left-10 w-72 h-72 bg-blue-400/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-pink-400/20 rounded-full blur-3xl animate-pulse delay-2000"></div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Logo - Horizontal */}
        <div className="flex justify-center mb-12 animate-fade-in">
          <div className="bg-white/95 backdrop-blur-md rounded-2xl px-8 py-5 flex items-center justify-center shadow-2xl hover:shadow-3xl transition-all duration-300 hover:scale-105">
            <HorizontalLogo logoSize={48} textSize="xl" />
          </div>
        </div>

        {/* Hero Section */}
        <div className="text-center text-white mb-20 animate-fade-in-up">
          <h1 className="text-6xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-blue-100 to-purple-100 bg-clip-text text-transparent">
            Eightfold AI
          </h1>
          <p className="text-3xl md:text-4xl mb-4 font-light text-white/90">
            Company Research Assistant
          </p>
          <p className="text-xl md:text-2xl text-blue-100 mb-10 max-w-2xl mx-auto">
            AI-Powered Account Plan Generator - Transform company research into actionable insights
          </p>
          <div className="flex items-center justify-center space-x-4 flex-wrap gap-4">
            <Link
              to="/register"
              className="group bg-white text-blue-600 px-10 py-4 rounded-xl font-semibold hover:bg-blue-50 transition-all duration-300 flex items-center space-x-2 shadow-xl hover:shadow-2xl hover:scale-105"
            >
              <span>Get Started</span>
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              to="/login"
              className="bg-transparent border-2 border-white text-white px-10 py-4 rounded-xl font-semibold hover:bg-white/20 transition-all duration-300 shadow-lg hover:shadow-xl hover:scale-105"
            >
              Login
            </Link>
          </div>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-8 mt-20">
          <div className="group bg-white/10 backdrop-blur-md rounded-2xl p-8 text-white border border-white/20 hover:bg-white/20 hover:scale-105 transition-all duration-300 shadow-xl hover:shadow-2xl">
            <div className="w-16 h-16 bg-white/20 rounded-xl flex items-center justify-center mb-6 group-hover:bg-white/30 transition-colors">
              <Search className="w-8 h-8 text-blue-200" />
            </div>
            <h3 className="text-2xl font-semibold mb-3">AI-Powered Research</h3>
            <p className="text-blue-100 leading-relaxed">
              Autonomous agent researches companies using multiple sources and RAG-powered knowledge retrieval for comprehensive insights
            </p>
          </div>
          <div className="group bg-white/10 backdrop-blur-md rounded-2xl p-8 text-white border border-white/20 hover:bg-white/20 hover:scale-105 transition-all duration-300 shadow-xl hover:shadow-2xl">
            <div className="w-16 h-16 bg-white/20 rounded-xl flex items-center justify-center mb-6 group-hover:bg-white/30 transition-colors">
              <FileText className="w-8 h-8 text-purple-200" />
            </div>
            <h3 className="text-2xl font-semibold mb-3">Account Plan Generation</h3>
            <p className="text-blue-100 leading-relaxed">
              Generate comprehensive, structured account plans with SWOT analysis, strategic recommendations, and actionable insights
            </p>
          </div>
          <div className="group bg-white/10 backdrop-blur-md rounded-2xl p-8 text-white border border-white/20 hover:bg-white/20 hover:scale-105 transition-all duration-300 shadow-xl hover:shadow-2xl">
            <div className="w-16 h-16 bg-white/20 rounded-xl flex items-center justify-center mb-6 group-hover:bg-white/30 transition-colors">
              <MessageSquare className="w-8 h-8 text-pink-200" />
            </div>
            <h3 className="text-2xl font-semibold mb-3">Voice & Chat Interface</h3>
            <p className="text-blue-100 leading-relaxed">
              Interact naturally through voice or text with real-time progress updates and seamless conversation flow
            </p>
          </div>
        </div>

        {/* Additional Features Grid */}
        <div className="grid md:grid-cols-4 gap-6 mt-16">
          {[
            { icon: Zap, title: 'Lightning Fast', desc: 'Quick research and analysis' },
            { icon: TrendingUp, title: 'Data-Driven', desc: 'Accurate insights and metrics' },
            { icon: Shield, title: 'Secure', desc: 'Your data is protected' },
            { icon: Sparkles, title: 'Smart AI', desc: 'Advanced AI capabilities' },
          ].map((feature, idx) => (
            <div key={idx} className="bg-white/5 backdrop-blur-sm rounded-xl p-6 text-white border border-white/10 hover:bg-white/10 transition-all duration-300">
              <feature.icon className="w-8 h-8 mb-3 text-blue-200" />
              <h4 className="font-semibold mb-2">{feature.title}</h4>
              <p className="text-sm text-blue-100">{feature.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

