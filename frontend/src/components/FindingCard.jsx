const SEVERITY_STYLES = {
  Critical: { dot: 'bg-rose', text: 'text-rose' },
  High: { dot: 'bg-amber', text: 'text-amber' },
  Medium: { dot: 'bg-blue', text: 'text-blue' },
}

const SEVERITY_DESCRIPTIONS = {
  Critical: 'Silent data corruption — invalidates scientific conclusions',
  High: 'Systematically biases results or inflates confidence',
  Medium: 'May affect reproducibility or specific edge cases',
}

export default function FindingCard({ finding }) {
  const styles = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.Medium
  const isFinding = finding.found

  return (
    <article className="py-5 border-b border-border last:border-b-0">
      <div className="flex items-start gap-3">
        <span
          className={[
            'inline-block w-2 h-2 rounded-full mt-2 shrink-0',
            isFinding ? styles.dot : 'bg-transparent border border-muted/40',
          ].join(' ')}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap mb-1.5">
            <span className="font-mono text-xs text-muted">{finding.pattern_id}</span>
            <h3
              className={[
                'font-semibold leading-snug flex-1',
                isFinding ? 'text-ink' : 'text-muted',
              ].join(' ')}
            >
              {finding.pattern_name}
            </h3>
            <span
              title={
                isFinding
                  ? SEVERITY_DESCRIPTIONS[finding.severity]
                  : 'This pattern was checked. No matching issue was found in the code.'
              }
              className={[
                'text-[11px] font-mono uppercase tracking-wider cursor-help',
                isFinding ? styles.text : 'text-muted/70',
              ].join(' ')}
            >
              {isFinding ? finding.severity : 'Clear'}
            </span>
          </div>

          <p
            className={[
              'text-sm',
              isFinding ? 'text-ink' : 'text-muted',
            ].join(' ')}
          >
            {finding.finding}
          </p>

          <div className="flex items-center justify-between text-xs text-muted mt-2">
            {finding.line_reference ? (
              <span className="font-mono">{finding.line_reference}</span>
            ) : (
              <span />
            )}
            <a
              href={finding.doc_link}
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-ink"
            >
              documentation →
            </a>
          </div>
        </div>
      </div>
    </article>
  )
}
