import './globals.css'
import Link from 'next/link'

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-8">
      <div className="max-w-4xl mx-auto text-center space-y-8">
        <h1 className="text-6xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
          CodeTraceX
        </h1>
        
        <p className="text-2xl text-slate-300 font-light">
          AI-powered repository intelligence for developers
        </p>
        
        <div className="mt-12 p-8 bg-slate-800/50 rounded-lg border border-slate-700">
          <h2 className="text-xl font-semibold mb-4 text-slate-200">
            Phase 1: GitHub Repository Ingestion
          </h2>
          <p className="text-slate-400 mb-6">
            Analyze public GitHub repositories and retrieve their metadata.
          </p>
          <Link 
            href="/repository"
            className="inline-block px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
          >
            Analyze Repository
          </Link>
        </div>

        <div className="mt-8 text-sm text-slate-500">
          <p>Built with Next.js and FastAPI</p>
        </div>
      </div>
    </main>
  )
}
