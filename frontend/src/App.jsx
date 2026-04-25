import { useState } from 'react'
import FileUploader from './components/FileUploader'
import FindingCard from './components/FindingCard'

const API_BASE = 'http://127.0.0.1:8000'
const DOMAINS = [
  { id: 'genomics', label: 'Genomics' },
  { id: 'neuroscience', label: 'Neuroscience' },
  { id: 'cardiac', label: 'Cardiac' },
]

export default function App() {
  const [mode, setMode] = useState('paste')      // 'paste' | 'files'
  const [code, setCode] = useState('')
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [domain, setDomain] = useState('genomics')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const canAnalyze =
    !loading && (mode === 'paste' ? code.trim().length > 0 : uploadedFiles.length > 0)

  async function analyze() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      let res
      if (mode === 'paste') {
        res = await fetch(`${API_BASE}/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, domain }),
        })
      } else {
        res = await fetch(`${API_BASE}/analyze/files`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ files: uploadedFiles, domain }),
        })
      }
      const data = await res.json()
      if (!res.ok) {
        const detail = data.detail
        const msg =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
            ? detail.map((e) => `${e.loc?.join('.')}: ${e.msg}`).join(' | ')
            : JSON.stringify(detail)
        throw new Error(msg ?? `HTTP ${res.status}`)
      }
      setResult(data)
    } catch (e) {
      setError(e.message ?? String(e))
    } finally {
      setLoading(false)
    }
  }

  const findingCount = result?.findings.filter((f) => f.found).length ?? 0

  return (
    <div className="min-h-screen bg-bg">
      <header className="max-w-[860px] mx-auto px-4 pt-10 pb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink leading-tight">SciCheck</h1>
          <p className="text-sm text-muted mt-0.5">Scientific code analyzer</p>
        </div>
        <nav className="flex items-center gap-5 text-sm text-muted">
          <a href="#" className="text-ink">Analyze</a>
          <a href="#" className="hover:text-ink">Patterns</a>
        </nav>
      </header>

      <main className="max-w-[860px] mx-auto px-4 pb-16">
        <section className="flex flex-col gap-4">

          {/* Domain selector */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-muted mr-1">Domain</span>
            {DOMAINS.map((d) => {
              const active = domain === d.id
              return (
                <button
                  key={d.id}
                  onClick={() => setDomain(d.id)}
                  className={[
                    'px-3.5 py-1.5 rounded-full text-sm border transition-colors',
                    active
                      ? 'bg-sage text-white border-sage'
                      : 'bg-surface text-muted border-border hover:text-ink',
                  ].join(' ')}
                >
                  {d.label}
                </button>
              )
            })}
          </div>

          {/* Mode toggle */}
          <div className="flex items-center gap-1 p-1 bg-surface border border-border rounded-lg w-fit">
            {['paste', 'files'].map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setResult(null); setError(null) }}
                className={[
                  'px-4 py-1.5 rounded text-sm transition-colors capitalize',
                  mode === m
                    ? 'bg-border text-ink'
                    : 'text-muted hover:text-ink',
                ].join(' ')}
              >
                {m === 'paste' ? 'Paste code' : 'Upload files'}
              </button>
            ))}
          </div>

          {/* Input area */}
          {mode === 'paste' ? (
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Paste your Python or R analysis code here"
              rows={14}
              className="w-full bg-surface border border-border rounded-lg p-4 font-mono text-sm text-ink placeholder:text-muted focus:outline-none focus:border-sage resize-y shadow-card"
            />
          ) : (
            <FileUploader files={uploadedFiles} onChange={setUploadedFiles} />
          )}

          {/* Actions */}
          <div className="flex items-center justify-between">
            <button
              onClick={analyze}
              disabled={!canAnalyze}
              className="inline-flex items-center gap-2 bg-sage text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-sage-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading && (
                <span
                  className="inline-block h-3.5 w-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin"
                  aria-hidden
                />
              )}
              {loading ? 'Analyzing…' : 'Analyze'}
            </button>
            {mode === 'paste' && (
              <a
                href="#"
                onClick={(e) => e.preventDefault()}
                className="text-sm text-muted underline hover:text-ink"
              >
                Load example with known bug →
              </a>
            )}
          </div>
        </section>

        {error && (
          <div className="mt-8 rounded-lg border border-rose/40 bg-rose/5 text-rose px-4 py-3 text-sm">
            Error: {error}
          </div>
        )}

        {result && (
          <section className="mt-10">
            <p className="text-xs text-muted mb-4">
              {result.patterns_checked} patterns checked · {findingCount}{' '}
              {findingCount === 1 ? 'finding' : 'findings'} ·{' '}
              {result.analysis_time_seconds}s
              {mode === 'files' && uploadedFiles.length > 0 && (
                <> · {uploadedFiles.length} {uploadedFiles.length === 1 ? 'file' : 'files'}</>
              )}
            </p>

            {result.clean ? (
              <div className="rounded-lg bg-cleanBg border border-border px-5 py-4 text-ink shadow-card">
                <span className="font-medium">✓ No issues found</span> across{' '}
                {result.patterns_checked} patterns.
              </div>
            ) : (
              <div className="border-t border-border">
                {[...result.findings]
                  .sort((a, b) => Number(b.found) - Number(a.found))
                  .map((f) => (
                    <FindingCard key={f.pattern_id} finding={f} />
                  ))}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  )
}
