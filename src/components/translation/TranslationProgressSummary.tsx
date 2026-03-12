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
    <div className="progress-board">
      <div className="progress-stats">
        <span>{progress.activeSegmentIndex ? `Segment ${progress.activeSegmentIndex}` : "Waiting"}</span>
        <span>{progress.totalSegments ? `${progress.completedSegments}/${progress.totalSegments} done` : "0/0 done"}</span>
        <span>{statusLabel}</span>
      </div>
      <div className="progress-rail">
        <div className="progress-fill" style={{ width: `${progressRatio}%` }} />
      </div>
      <div className="segment-card">
        <p className="segment-label">Current Source</p>
        <p>{sourcePreview}</p>
        <p className="segment-label">Current Target</p>
        <p>{targetPreview}</p>
      </div>
    </div>
  );
}
