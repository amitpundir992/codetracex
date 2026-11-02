import Link from 'next/link'
import { ArrowRight, GitBranch, Search, Zap, Brain, Shield, BarChart3 } from 'lucide-react'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 via-white to-slate-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-20 lg:py-32">
        <div className="max-w-5xl mx-auto text-center space-y-8">
          {/* Logo */}
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl shadow-2xl">
              <GitBranch className="w-12 h-12 text-white" />
            </div>
          </div>

          {/* Main Heading */}
          <div className="space-y-4">
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight">
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600">
                CodeTraceX
              </span>
            </h1>
            <p className="text-xl sm:text-2xl lg:text-3xl text-slate-600 dark:text-slate-400 font-light max-w-3xl mx-auto">
              AI-powered repository intelligence for modern development teams
            </p>
          </div>

          {/* Subtitle */}
          <p className="text-base sm:text-lg text-slate-500 dark:text-slate-500 max-w-2xl mx-auto">
            Understand your codebase instantly. Trace dependencies effortlessly. 
            Predict impact accurately. Built with AI and designed for developers.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-6">
            <Link 
              href="/repository"
              className="group inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-xl transition-all transform hover:scale-105 shadow-lg hover:shadow-xl"
            >
              Get Started
              <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <a 
              href="https://github.com/yourusername/CodeTraceX"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 hover:border-blue-500 dark:hover:border-blue-500 text-slate-700 dark:text-slate-300 font-semibold rounded-xl transition-all"
            >
              <GitBranch className="w-5 h-5" />
              View on GitHub
            </a>
          </div>

          {/* Trust Indicators */}
          <div className="pt-12 flex flex-wrap justify-center items-center gap-8 text-sm text-slate-500 dark:text-slate-600">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4" />
              <span>Open Source</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4" />
              <span>Fast Analysis</span>
            </div>
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4" />
              <span>AI-Powered</span>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="container mx-auto px-4 py-20 lg:py-24">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything you need to understand code
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-400">
              Powerful features to help you navigate and analyze any repository
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="group p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-500 transition-all hover:shadow-lg">
              <div className="p-3 bg-blue-100 dark:bg-blue-950 rounded-lg w-fit mb-4">
                <Search className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Smart Code Analysis</h3>
              <p className="text-slate-600 dark:text-slate-400">
                Automatically scan and analyze repositories. Extract symbols, detect patterns, and map dependencies.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="group p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-purple-500 dark:hover:border-purple-500 transition-all hover:shadow-lg">
              <div className="p-3 bg-purple-100 dark:bg-purple-950 rounded-lg w-fit mb-4">
                <Brain className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">AI Assistant</h3>
              <p className="text-slate-600 dark:text-slate-400">
                Ask questions about your codebase. Get instant answers with citations from actual source code.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="group p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-green-500 dark:hover:border-green-500 transition-all hover:shadow-lg">
              <div className="p-3 bg-green-100 dark:bg-green-950 rounded-lg w-fit mb-4">
                <GitBranch className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Dependency Tracing</h3>
              <p className="text-slate-600 dark:text-slate-400">
                Visualize code relationships. Trace function calls, imports, and dependencies across your project.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="group p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-orange-500 dark:hover:border-orange-500 transition-all hover:shadow-lg">
              <div className="p-3 bg-orange-100 dark:bg-orange-950 rounded-lg w-fit mb-4">
                <BarChart3 className="w-6 h-6 text-orange-600 dark:text-orange-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Impact Analysis</h3>
              <p className="text-slate-600 dark:text-slate-400">
                Predict the impact of code changes. Identify affected components before making modifications.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="group p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-pink-500 dark:hover:border-pink-500 transition-all hover:shadow-lg">
              <div className="p-3 bg-pink-100 dark:bg-pink-950 rounded-lg w-fit mb-4">
                <Zap className="w-6 h-6 text-pink-600 dark:text-pink-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Lightning Fast</h3>
              <p className="text-slate-600 dark:text-slate-400">
                Powered by tree-sitter and optimized algorithms. Analyze large repositories in seconds.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="group p-6 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 hover:border-indigo-500 dark:hover:border-indigo-500 transition-all hover:shadow-lg">
              <div className="p-3 bg-indigo-100 dark:bg-indigo-950 rounded-lg w-fit mb-4">
                <Shield className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Secure & Private</h3>
              <p className="text-slate-600 dark:text-slate-400">
                Your code stays safe. We analyze structure and metadata without storing source code.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="container mx-auto px-4 py-20">
        <div className="max-w-4xl mx-auto text-center">
          <div className="p-12 bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 rounded-3xl shadow-2xl">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
              Ready to explore your codebase?
            </h2>
            <p className="text-xl text-blue-100 mb-8">
              Start analyzing repositories in seconds
            </p>
            <Link 
              href="/repository"
              className="inline-flex items-center gap-2 px-8 py-4 bg-white text-blue-600 font-semibold rounded-xl hover:bg-blue-50 transition-all transform hover:scale-105 shadow-lg"
            >
              Analyze Your First Repository
              <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="container mx-auto px-4 py-12 border-t border-slate-200 dark:border-slate-800">
        <div className="max-w-6xl mx-auto text-center text-sm text-slate-500 dark:text-slate-600">
          <p className="mb-4">
            Built with <span className="text-red-500">♥</span> using Next.js, FastAPI, and AI
          </p>
          <div className="flex justify-center gap-6">
            <a href="#" className="hover:text-blue-600 transition-colors">Documentation</a>
            <a href="#" className="hover:text-blue-600 transition-colors">GitHub</a>
            <a href="#" className="hover:text-blue-600 transition-colors">API</a>
          </div>
        </div>
      </footer>
    </main>
  )
}
