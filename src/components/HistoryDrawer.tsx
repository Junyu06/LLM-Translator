import { useEffect, useRef, useState } from "react";

import type { StringKey } from "../i18n";
import type { HistoryItem } from "../types";
import { IconSearch, IconTrash, IconX } from "../icons";

type T = (key: StringKey, values?: Record<string, string | number>) => string;

type Props = {
  t: T;
  // The drawer starts below the top bar, so the History button stays clickable and closes it.
  top: number;
  history: HistoryItem[];
  onOpen: (item: HistoryItem) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  onClose: () => void;
};

const oneLine = (text: string) => text.replace(/\s+/g, " ");

// Remember where the list was scrolled between openings.
let savedScrollTop = 0;

export default function HistoryDrawer({ t, top, history, onOpen, onDelete, onClear, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = savedScrollTop;
  }, []);

  const close = () => onClose();

  const term = query.trim().toLowerCase();
  const items = term
    ? history.filter((item) => item.source.toLowerCase().includes(term) || item.target.toLowerCase().includes(term))
    : history;

  return (
    <div className="overlay-mask drawer-mask" style={{ top }} onClick={close}>
      <div className="drawer-card" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-top-row">
            <h2 className="settings-title">{t("history")}</h2>
            <button className="icon-btn" onClick={close} title={t("close")}><IconX /></button>
          </div>
          {history.length > 0 && (
            <div className="history-search-container">
              <span className="search-icon"><IconSearch /></span>
              <input className="history-search-input" placeholder={t("history_search")} value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
          )}
        </div>
        {/* Saved while scrolling, so the position survives however the drawer closes. */}
        <div className="history-list" ref={listRef} onScroll={(e) => { savedScrollTop = e.currentTarget.scrollTop; }}>
          {items.length === 0 ? (
            <div className="empty-hint">{history.length === 0 ? t("history_empty") : t("history_no_match")}</div>
          ) : (
            items.map((item) => (
              <div key={item.id} className="history-item" onClick={() => { onOpen(item); close(); }}>
                <div className="history-content">
                  <div className="history-target">{oneLine(item.target)}</div>
                  <div className="history-source">{oneLine(item.source)}</div>
                </div>
                <button
                  className="history-delete-btn"
                  title={t("delete")}
                  onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
                >
                  <IconTrash />
                </button>
              </div>
            ))
          )}
        </div>
        {history.length > 0 && (
          <div className="drawer-footer">
            {confirmClear ? (
              <>
                <span className="drawer-footer-note">{t("history_confirm_note", { count: history.length })}</span>
                <button className="secondary-btn-sm" onClick={() => setConfirmClear(false)}>{t("cancel")}</button>
                <button className="secondary-btn-sm danger-btn" onClick={() => { onClear(); setConfirmClear(false); }}>{t("history_confirm_clear")}</button>
              </>
            ) : (
              <button className="text-btn" onClick={() => setConfirmClear(true)}><IconTrash /> {t("history_clear")}</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
