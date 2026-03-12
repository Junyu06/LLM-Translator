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
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Control Deck</p>
          <h2 className="section-title">Translation settings</h2>
        </div>
        <button className="ghost" type="button" onClick={onSwapLanguages} disabled={swapDisabled}>
          Swap languages
        </button>
      </div>

      {settings}
      {input}
      {actions}
    </>
  );
}
