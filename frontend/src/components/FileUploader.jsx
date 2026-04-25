import { useRef, useState } from 'react'

const ACCEPTED_EXT = ['.py', '.r', '.rmd', '.qmd']

function isAccepted(name) {
  const lower = name.toLowerCase()
  return ACCEPTED_EXT.some((ext) => lower.endsWith(ext))
}

async function readEntry(entry) {
  if (entry.isFile) {
    return new Promise((resolve) => entry.file(resolve))
  }
  if (entry.isDirectory) {
    const reader = entry.createReader()
    const entries = await new Promise((resolve) =>
      reader.readEntries(resolve)
    )
    const nested = await Promise.all(entries.map(readEntry))
    return nested.flat()
  }
  return []
}

async function filesToObjects(rawFiles) {
  const results = []
  for (const f of rawFiles) {
    if (!isAccepted(f.name)) continue
    const content = await f.text()
    if (!content.trim()) continue          // skip empty files like __init__.py
    results.push({ name: f.name, content })
  }
  return results
}

export default function FileUploader({ files, onChange }) {
  const fileInputRef = useRef(null)
  const folderInputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  function merge(incoming) {
    const existing = new Set(files.map((f) => f.name))
    const fresh = incoming.filter((f) => !existing.has(f.name))
    if (fresh.length) onChange([...files, ...fresh])
  }

  async function handleFileInput(raw) {
    const objs = await filesToObjects(raw)
    merge(objs)
  }

  async function onDrop(e) {
    e.preventDefault()
    setDragging(false)

    // Use FileSystem API to support folder drops
    const items = [...(e.dataTransfer.items ?? [])]
    const hasEntries = items.length > 0 && typeof items[0].webkitGetAsEntry === 'function'

    if (hasEntries) {
      const allFiles = (
        await Promise.all(items.map((i) => readEntry(i.webkitGetAsEntry())))
      ).flat()
      const objs = await filesToObjects(allFiles)
      merge(objs)
    } else {
      const objs = await filesToObjects(e.dataTransfer.files)
      merge(objs)
    }
  }

  function remove(name) {
    onChange(files.filter((f) => f.name !== name))
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={[
          'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed',
          'py-10 transition-colors select-none',
          dragging
            ? 'border-sage bg-sage/10'
            : 'border-border bg-surface',
        ].join(' ')}
      >
        <span className="text-sm text-muted text-center">
          Drop <span className="text-ink">.py</span> or{' '}
          <span className="text-ink">.R</span> files or a{' '}
          <span className="text-ink">folder</span> here
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="px-3 py-1.5 rounded text-xs border border-border bg-border/40 text-muted hover:text-ink transition-colors"
          >
            Browse files
          </button>
          <button
            type="button"
            onClick={() => folderInputRef.current?.click()}
            className="px-3 py-1.5 rounded text-xs border border-border bg-border/40 text-muted hover:text-ink transition-colors"
          >
            Browse folder
          </button>
        </div>
        <span className="text-xs text-muted/60">
          .py · .R · .Rmd · .qmd · empty files skipped automatically
        </span>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXT.join(',')}
          className="hidden"
          onChange={(e) => handleFileInput(e.target.files)}
        />
        <input
          ref={folderInputRef}
          type="file"
          multiple
          webkitdirectory=""
          className="hidden"
          onChange={(e) => handleFileInput(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <div className="flex flex-col gap-1">
          <p className="text-xs text-muted px-1">{files.length} file{files.length !== 1 ? 's' : ''} loaded</p>
          <ul className="flex flex-col gap-1 max-h-64 overflow-y-auto">
            {files.map((f) => (
              <li
                key={f.name}
                className="flex items-center justify-between gap-3 rounded px-3 py-2 bg-surface border border-border text-sm"
              >
                <span className="font-mono text-ink truncate">{f.name}</span>
                <button
                  onClick={() => remove(f.name)}
                  className="text-muted hover:text-rose shrink-0 transition-colors"
                  aria-label={`Remove ${f.name}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
