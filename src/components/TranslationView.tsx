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

const LINK_DEFINITION_RE = /^ {0,3}\[[^\]]+\]:\s*\S.*$/gm;

// Each block is rendered on its own, so reference links (`[text][name]`) get
// the whole document's definitions appended; definitions render nothing.
const Prose = ({ text, markdown, links = "" }: { text: string; markdown: boolean; links?: string }) =>
  markdown
    ? <div className="markdown-body"><ReactMarkdown>{links ? `${text}\n\n${links}` : text}</ReactMarkdown></div>
    : <>{text}</>;

// A paragraph still waiting for its translation.
const Pending = () => <span className="pending" aria-hidden="true" />;

export default function TranslationView({ segments, outputText, bilingual, markdown, running, emptyHint }: Props) {
  const links = markdown ? segments.flatMap((segment) => segment.source.match(LINK_DEFINITION_RE) ?? []).join("\n") : "";

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
              <Prose text={segment.source} markdown={markdown} links={links} />
            </section>
          ) : (
            <section key={index} className="pair">
              <div className="pair-source"><Prose text={segment.source} markdown={markdown} links={links} /></div>
              <div className="pair-target">
                {segment.target ? <Prose text={segment.target} markdown={markdown} links={links} /> : running && <Pending />}
              </div>
            </section>
          )
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
            <Prose text={segment.target} markdown={markdown} links={links} />
          </div>
        );
      })}
    </div>
  );
}
