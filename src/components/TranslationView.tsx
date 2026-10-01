import ReactMarkdown from "react-markdown";

import type { TranslationSegment } from "../types";

type Props = {
  segments: TranslationSegment[];
  outputText: string;
  bilingual: boolean;
  markdown: boolean;
  running: boolean;
  emptyHint: string;
};

const Prose = ({ text, markdown }: { text: string; markdown: boolean }) =>
  markdown ? <div className="markdown-body"><ReactMarkdown>{text}</ReactMarkdown></div> : <>{text}</>;

// A paragraph still waiting for its translation.
const Pending = () => <span className="pending" aria-hidden="true" />;

export default function TranslationView({ segments, outputText, bilingual, markdown, running, emptyHint }: Props) {
  if (segments.length === 0) {
    if (outputText) {
      return <div className="translation"><div className="paragraph"><Prose text={outputText} markdown={markdown} /></div></div>;
    }
    return running ? <div className="translation"><Pending /></div> : <p className="empty-hint">{emptyHint}</p>;
  }

  if (bilingual) {
    return (
      <div className="translation bilingual">
        {segments.map((segment, index) =>
          segment.source.trim() ? (
            <section key={index} className="pair">
              <div className="pair-source"><Prose text={segment.source} markdown={markdown} /></div>
              <div className="pair-target">
                {segment.target ? <Prose text={segment.target} markdown={markdown} /> : running && <Pending />}
              </div>
            </section>
          ) : null
        )}
      </div>
    );
  }

  // Translation only. Code and other passthrough blocks keep their place.
  const firstPending = segments.findIndex((segment) => segment.source.trim() && !segment.target);
  return (
    <div className="translation">
      {segments.map((segment, index) => {
        if (!segment.source.trim()) return <div key={index} className="gap" />;
        if (!segment.target) return running && index === firstPending ? <Pending key={index} /> : null;
        return (
          <div key={index} className="paragraph">
            <Prose text={segment.target} markdown={markdown} />
          </div>
        );
      })}
    </div>
  );
}
