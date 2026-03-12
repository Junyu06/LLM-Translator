import type { ClipboardEventHandler, ChangeEventHandler } from "react";

type InputEditorProps = {
  value: string;
  rows?: number;
  onChange: ChangeEventHandler<HTMLTextAreaElement>;
  onPaste: ClipboardEventHandler<HTMLTextAreaElement>;
};

export function InputEditor({ value, rows = 12, onChange, onPaste }: InputEditorProps) {
  return (
    <label className="field">
      <span className="field-label">Input</span>
      <textarea value={value} onChange={onChange} onPaste={onPaste} rows={rows} />
    </label>
  );
}
