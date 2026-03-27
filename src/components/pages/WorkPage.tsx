import type { FormEvent, ReactNode } from "react";

type WorkPageProps = {
  controls: ReactNode;
  output: ReactNode;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function WorkPage({ controls, output, onSubmit }: WorkPageProps) {
  return (
    <div className="work-layout">
      <form className="work-panel panel" onSubmit={onSubmit}>
        {controls}
      </form>

      <div className="work-panel panel">
        {output}
      </div>
    </div>
  );
}
