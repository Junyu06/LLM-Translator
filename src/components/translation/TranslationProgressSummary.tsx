type ProgressState = {
  totalSegments: number;
  completedSegments: number;
  activeSegmentIndex: number | null;
  activeSegmentSource: string;
  activeSegmentTarget: string;
  segmentStatus: string;
  partial: boolean;
};

type TranslationProgressSummaryProps = {
  progress: ProgressState;
  progressRatio: number;
  statusLabel: string;
  sourcePreview: string;
  targetPreview: string;
};

export function TranslationProgressSummary({
  progress,
  progressRatio,
  statusLabel,
  sourcePreview,
  targetPreview
}: TranslationProgressSummaryProps) {
  return (
    <div className="progress-board" style={{display: 'flex', flexDirection: 'column', gap: '16px'}}>
      <div className="progress-stats">
        <span>{progress.activeSegmentIndex ? `Segment ${progress.activeSegmentIndex}` : "Idle"}</span>
        <span>{progress.totalSegments ? `${progress.completedSegments}/${progress.totalSegments} Segments` : "0/0 Segments"}</span>
      </div>
      
      <div className="progress-rail">
        <div className="progress-fill" style={{ width: `${progressRatio}%` }} />
      </div>

      <div style={{fontSize: '0.75rem', color: 'var(--ink-muted)', textAlign: 'center'}}>
        {statusLabel}
      </div>

      <div className="panel" style={{padding: '12px', background: 'var(--bg-app)', display: 'flex', flexDirection: 'column', gap: '8px'}}>
        <div className="field">
          <span className="section-kicker">Current Segment Source</span>
          <div style={{fontSize: '0.85rem', color: 'var(--ink-secondary)', minHeight: '1.2em'}}>
            {sourcePreview}
          </div>
        </div>
        <div className="field" style={{marginTop: '4px'}}>
          <span className="section-kicker">Current Segment Target</span>
          <div style={{fontSize: '0.85rem', color: 'var(--ink-primary)', fontWeight: '500', minHeight: '1.2em'}}>
            {targetPreview}
          </div>
        </div>
      </div>
    </div>
  );
}
