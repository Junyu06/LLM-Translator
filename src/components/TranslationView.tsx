import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { StringKey } from "../i18n";
import { IconCopy, IconRefresh, IconSource } from "../icons";
import type { TranslationSegment } from "../types";

type T = (key: StringKey, values?: Record<string, string | number>) => string;

type Props = {
  t: T;
  segments: TranslationSegment[];
  outputText: string;
  bilingual: boolean;
  markdown: boolean;
  running: boolean;
  // Paragraphs being translated again on their own.
  retranslating: Set<number>;
  // Per-paragraph buttons; off in the quick window.
  actions?: boolean;
  onCopy: (index: number) => void;
  onRetranslate: (index: number) => void;
  emptyHint: string;
};

// Tables, strikethrough, task lists and autolinks, as on GitHub.
const GFM = [remarkGfm];

const Prose = ({ text, markdown }: { text: string; markdown: boolean }) =>
  markdown ? <div className="markdown-body"><ReactMarkdown remarkPlugins={GFM}>{text}</ReactMarkdown></div> : <>{text}</>;

// A paragraph still waiting for its translation.
const Pending = () => <span className="pending" aria-hidden="true" />;

type ActionsProps = {
  t: T;
  index: number;
  busy: boolean;
  showingSource?: boolean;
  onToggleSource?: () => void;
  onCopy: (index: number) => void;
  onRetranslate: (index: number) => void;
};

// Shown when the pointer is over a paragraph.
const Actions = ({ t, index, busy, showingSource, onToggleSource, onCopy, onRetranslate }: ActionsProps) => (
  <span className="para-actions">
    {onToggleSource && (
      <button className={`para-btn${showingSource ? " active" : ""}`} onClick={onToggleSource} title={t(showingSource ? "hide_original" : "show_original")}>
        <IconSource />
      </button>
    )}
    <button className="para-btn" onClick={() => onCopy(index)} title={t("copy_paragraph")} disabled={busy}><IconCopy /></button>
    <button className="para-btn" onClick={() => onRetranslate(index)} title={t("retranslate")} disabled={busy}><IconRefresh /></button>
  </span>
);

export default function TranslationView(props: Props) {
  const { t, segments, outputText, bilingual, markdown, running, retranslating, onCopy, onRetranslate, emptyHint, actions = true } = props;
  // Paragraphs whose original is shown inline in the translation-only view.
  const [openSources, setOpenSources] = useState<Set<number>>(new Set());
  const toggleSource = (index: number) =>
    setOpenSources((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  if (segments.length === 0) {
    if (outputText) {
      return <div className="translation"><div className="para"><Prose text={outputText} markdown={markdown} /></div></div>;
    }
    return running ? <div className="translation"><Pending /></div> : <p className="empty-hint">{emptyHint}</p>;
  }

  // A finished paragraph can be copied or translated again, unless the whole text is still running.
  const isKept = (segment: TranslationSegment) => segment.kept ?? segment.target === segment.source;
  const actionable = (segment: TranslationSegment) => actions && !running && segment.done && !isKept(segment);

  if (bilingual) {
    return (
      <div className="translation bilingual">
        {segments.map((segment, index) => {
          if (!segment.source.trim()) return null;
          const busy = retranslating.has(index);
          if (segment.done && isKept(segment) && !busy) {
            // Code and other kept-as-is blocks appear once.
            return (
              <section key={index} className="pair">
                <Prose text={segment.source} markdown={markdown} />
              </section>
            );
          }
          return (
            <section key={index} className="pair">
              <div className="pair-source"><Prose text={segment.source} markdown={markdown} /></div>
              <div className="pair-target para">
                {busy ? <Pending /> : segment.target ? <Prose text={segment.target} markdown={markdown} /> : running && <Pending />}
                {actionable(segment) && <Actions t={t} index={index} busy={busy} onCopy={onCopy} onRetranslate={onRetranslate} />}
              </div>
            </section>
          );
        })}
      </div>
    );
  }

  // Translation only, Markdown: one document. Blocks are pieces of one
  // structure (a list split around its code, a definition used elsewhere), so
  // rendering them apart breaks it; per-block actions live in the side-by-side
  // view. Blocks show up to the first one still waiting, so a code block (kept
  // as-is from the start) does not jump ahead of untranslated text.
  if (markdown) {
    const firstWaiting = segments.findIndex((segment, index) => segment.source.trim() && (!segment.target || retranslating.has(index)));
    const shown = firstWaiting === -1 ? segments : segments.slice(0, firstWaiting);
    const done = shown.map((segment) => segment.target).filter(Boolean).join("\n\n");
    const waiting = (running || retranslating.size > 0) && firstWaiting !== -1;
    return (
      <div className="translation reading">
        {done && <Prose text={done} markdown />}
        {waiting && <Pending />}
      </div>
    );
  }

  // Translation only. Lines that follow each other in the source stay
  // together; a blank line in the source starts a new group with more space,
  // so the translation keeps the source's shape.
  const groups: number[][] = [];
  segments.forEach((segment, index) => {
    if (!segment.source.trim()) {
      if (groups.length && groups[groups.length - 1].length) groups.push([]);
      return;
    }
    if (!groups.length) groups.push([]);
    groups[groups.length - 1].push(index);
  });
  const firstPending = segments.findIndex((segment) => segment.source.trim() && !segment.target);

  return (
    <div className="translation reading">
      {groups.filter((group) => group.length).map((group) => (
        <div key={group[0]} className="group">
          {group.map((index) => {
            const segment = segments[index];
            const busy = retranslating.has(index);
            if (!segment.target && !busy) {
              return running && index === firstPending ? <div key={index} className="para"><Pending /></div> : null;
            }
            const showingSource = openSources.has(index);
            return (
              <div key={index} className={`para${showingSource ? " with-source" : ""}`}>
                {showingSource && <div className="para-source">{segment.source}</div>}
                {busy ? <Pending /> : segment.target}
                {actionable(segment) && (
                  <Actions
                    t={t}
                    index={index}
                    busy={busy}
                    showingSource={showingSource}
                    onToggleSource={() => toggleSource(index)}
                    onCopy={onCopy}
                    onRetranslate={onRetranslate}
                  />
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
