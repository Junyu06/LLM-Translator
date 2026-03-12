import type { FormEvent, ReactNode } from "react";

type WorkPageProps = {
  controls: ReactNode;
  output: ReactNode;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function WorkPage({ controls, output, onSubmit }: WorkPageProps) {
  return (
    <div className="work-layout work-stage">
      <form className="panel controls work-panel work-panel-controls" onSubmit={onSubmit}>
        {controls}
      </form>

      <section className="panel output work-panel work-panel-output">{output}</section>
    </div>
  );
}
