type OutputPanelProps = {
  detectedSourceLanguage?: string | null;
  output: string;
  onCopy: () => void;
};

export function OutputPanel({ detectedSourceLanguage, output, onCopy }: OutputPanelProps) {
  return (
    <>
      <div className="output-header">
        <div>
          <h2 className="section-title">Result</h2>
          <span className="eyebrow" style={{color: 'var(--ink-muted)'}}>
            {detectedSourceLanguage ? `Detected: ${detectedSourceLanguage}` : "Awaiting input"}
          </span>
        </div>
        <button className="primary" type="button" onClick={onCopy} disabled={!output.trim()}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px', verticalAlign: 'middle'}}>
            <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
          </svg>
          Copy
        </button>
      </div>
      <pre style={{flex: 1, minHeight: '300px'}}>
        {output || "The translation result will appear here, segment by segment..."}
      </pre>
    </>
  );
}
