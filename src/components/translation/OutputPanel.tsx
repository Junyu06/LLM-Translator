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
          <p className="section-kicker">Output</p>
          <h2 className="section-title">Rendered translation</h2>
        </div>
        <div className="output-tools">
          <span className="output-meta">{detectedSourceLanguage ? `Detected: ${detectedSourceLanguage}` : "Awaiting input"}</span>
          <button className="ghost action-button" type="button" onClick={onCopy}>
            Copy output
          </button>
        </div>
      </div>
      <pre>{output || "Translation result will appear here, segment by segment."}</pre>
    </>
  );
}
