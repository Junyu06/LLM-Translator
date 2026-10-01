import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { TranslationSegment } from "../types";

type Props = {
  segments: TranslationSegment[];
  outputText: string;
  bilingual: boolean;
  markdown: boolean;
  running: boolean;
  emptyHint: string;
};

// Tables, strikethrough, task lists and autolinks, as on GitHub.
const GFM = [remarkGfm];

const Prose = ({ text, markdown }: { text: string; markdown: boolean }) =>
  markdown ? <div className="markdown-body"><ReactMarkdown remarkPlugins={GFM}>{text}</ReactMarkdown></div> : <>{text}</>;

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
          !segment.source.trim() ? null : segment.done && segment.target === segment.source ? (
            // Code and other kept-as-is blocks appear once.
            <section key={index} className="pair">
              <Prose text={segment.source} markdown={markdown} />
            </section>
          ) : (
            <section key={index} className="pair">
              <div className="pair-source"><Prose text={segment.source} markdown={markdown} /></div>
              <div className="pair-target">
                {segment.target ? <Prose text={segment.target} markdown={markdown} /> : running && <Pending />}
              </div>
            </section>
          )
        )}
      </div>
    );
  }

  // Translation only, Markdown: one document, so anything that spans blocks
  // (reference definitions, list numbering) renders as in the source.
  if (markdown) {
    // Show blocks in order up to the first one still waiting, so a code block
    // (kept as-is from the start) does not jump ahead of untranslated text.
    const firstWaiting = segments.findIndex((segment) => segment.source.trim() && !segment.target);
    const shown = firstWaiting === -1 ? segments : segments.slice(0, firstWaiting);
    const done = shown.map((segment) => segment.target).filter(Boolean).join("\n\n");
    const waiting = running && firstWaiting !== -1;
    return (
      <div className="translation">
        {done && <Prose text={done} markdown />}
        {waiting && <Pending />}
      </div>
    );
  }

  // Translation only. Blank lines keep their place.
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
