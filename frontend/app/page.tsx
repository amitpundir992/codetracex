import './globals.css'

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
            Coming Soon
          </h2>
          <p className="text-slate-400">
            Repository analysis and intelligence features will be added in future phases.
          </p>
          <p className="text-slate-400 mt-2">
            This platform will help you understand unfamiliar codebases, analyze dependencies, 
            and answer questions about your repositories.
          </p>
        </div>

        <div className="mt-8 text-sm text-slate-500">
          <p>Built with Next.js and FastAPI</p>
        </div>
      </div>
    </main>
  )
}
