import type { ReactNode } from "react";

type TranslationControlsProps = {
  onSwapLanguages: () => void;
  swapDisabled: boolean;
  settings: ReactNode;
  input: ReactNode;
  actions: ReactNode;
};

export function TranslationControls({
  onSwapLanguages,
  swapDisabled,
  settings,
  input,
  actions
}: TranslationControlsProps) {
  return (
    <>
      <div className="output-header">
        <h2 className="section-title">Translation Setup</h2>
        <button className="ghost" type="button" onClick={onSwapLanguages} disabled={swapDisabled}>
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px', verticalAlign: 'middle'}}>
            <path d="M7 16V4M7 4L3 8M7 4L11 8M17 8v12M17 20l4-4M17 20l-4-4"/>
          </svg>
          Swap Languages
        </button>
      </div>

      {settings}
      {input}
      <div style={{marginTop: 'auto', paddingTop: '20px'}}>
        {actions}
      </div>
    </>
  );
}
