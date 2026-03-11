import type { FormEvent, ReactNode } from "react";

type WorkPageProps = {
  controls: ReactNode;
  output: ReactNode;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function WorkPage({ controls, output, onSubmit }: WorkPageProps) {
  return (
    <>
      <form className="panel controls" onSubmit={onSubmit}>
        {controls}
      </form>

      <section className="panel output">{output}</section>
    </>
  );
}
