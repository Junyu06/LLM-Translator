type StatusBarProps = {
  status: string;
  isReady: boolean;
};

export function StatusBar({ status, isReady }: StatusBarProps) {
  return <div className={`status-pill ${isReady ? "ready" : "pending"}`}>{status}</div>;
}
