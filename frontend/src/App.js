import { useState, useRef, useEffect, useCallback } from "react";
import "./App.css";

const API = "http://localhost:8000";
const MIN_PREVIEW_W = 200;
const MAX_PREVIEW_W = 700;
const DEFAULT_PREVIEW_W = 380;

export default function App() {
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Preview state
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const pageRef = useRef(0);
  const tableWrapRef = useRef(null);

  // Sidebar state
  const [history, setHistory] = useState([]);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [downloadReady, setDownloadReady] = useState(false);

  // Resize state
  const [previewWidth, setPreviewWidth] = useState(DEFAULT_PREVIEW_W);
  const isDragging = useRef(false);
  const dragStartX = useRef(0);
  const dragStartW = useRef(DEFAULT_PREVIEW_W);

  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Resize ────────────────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e) => {
    isDragging.current = true;
    dragStartX.current = e.clientX;
    dragStartW.current = previewWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [previewWidth]);

  useEffect(() => {
    const onMouseMove = (e) => {
      if (!isDragging.current) return;
      const delta = dragStartX.current - e.clientX;
      const newW = Math.min(MAX_PREVIEW_W, Math.max(MIN_PREVIEW_W, dragStartW.current + delta));
      setPreviewWidth(newW);
    };
    const onMouseUp = () => {
      if (!isDragging.current) return;
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  // ── Paginated Preview ─────────────────────────────────────────────────────────
  async function fetchPreview(sessionId) {
    pageRef.current = 0;
    setRows([]);
    setColumns([]);
    setHasMore(false);
    try {
      const res = await fetch(`${API}/preview/${sessionId}?page=0`);
      if (res.ok) {
        const data = await res.json();
        setColumns(data.columns);
        setRows(data.rows);
        setTotalRows(data.total_rows);
        setHasMore(data.has_more);
        pageRef.current = 1;
        // Scroll table back to top on refresh
        if (tableWrapRef.current) tableWrapRef.current.scrollTop = 0;
      }
    } catch (_) {}
  }

  async function fetchNextPage(sessionId) {
    if (!hasMore || loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await fetch(`${API}/preview/${sessionId}?page=${pageRef.current}`);
      if (res.ok) {
        const data = await res.json();
        setRows((prev) => [...prev, ...data.rows]);
        setHasMore(data.has_more);
        pageRef.current += 1;
      }
    } catch (_) {}
    setLoadingMore(false);
  }

  // Infinite scroll — load next page when user scrolls near bottom of table
  const onTableScroll = useCallback(() => {
    const el = tableWrapRef.current;
    if (!el || !session) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) {
      fetchNextPage(session.session_id);
    }
  }, [session, hasMore, loadingMore]);

  // ── Operation History ─────────────────────────────────────────────────────────
  async function fetchHistory(sessionId) {
    try {
      const res = await fetch(`${API}/history/steps/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data.steps || []);
        setCanUndo(data.can_undo);
        setCanRedo(data.can_redo);
      }
    } catch (_) {}
  }

  // ── File Upload ───────────────────────────────────────────────────────────────
  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setMessages([]);
    setDownloadReady(false);
    setRows([]);
    setColumns([]);

    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/upload`, { method: "POST", body: form });
      const data = await res.json();
      setSession(data);
      setMessages([{ role: "assistant", text: data.opening_message }]);
      await fetchPreview(data.session_id);
      await fetchHistory(data.session_id);
    } catch (err) {
      setMessages([{ role: "assistant", text: "Upload failed. Is the server running?" }]);
    }
    setUploading(false);
    e.target.value = "";
  }

  // ── Chat ──────────────────────────────────────────────────────────────────────
  async function handleSend() {
    if (!input.trim() || !session || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", text: userMsg }]);
    setLoading(true);
    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session.session_id, message: userMsg }),
      });
      const data = await res.json();
      setMessages((m) => [...m, { role: "assistant", text: data.reply }]);
      if (data.download_ready) {
        setDownloadReady(true);
        await fetchPreview(session.session_id);
        await fetchHistory(session.session_id);
      }
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Error contacting server." }]);
    }
    setLoading(false);
  }

  // ── Undo / Redo ───────────────────────────────────────────────────────────────
  async function handleUndo() {
    if (!session) return;
    const res = await fetch(`${API}/history/undo/${session.session_id}`, { method: "POST" });
    if (res.ok) {
      setMessages((m) => [...m, { role: "assistant", text: "↩ Undone." }]);
      await fetchPreview(session.session_id);
      await fetchHistory(session.session_id);
    }
  }

  async function handleRedo() {
    if (!session) return;
    const res = await fetch(`${API}/history/redo/${session.session_id}`, { method: "POST" });
    if (res.ok) {
      setMessages((m) => [...m, { role: "assistant", text: "↪ Redone." }]);
      await fetchPreview(session.session_id);
      await fetchHistory(session.session_id);
    }
  }

  function handleDownload() { window.open(`${API}/download/${session.session_id}`, "_blank"); }
  function handleNotebook() { window.open(`${API}/notebook/${session.session_id}`, "_blank"); }

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="app" style={{ "--preview-w": `${previewWidth}px` }}>

      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-icon">⬡</span>
          <span className="logo-text">DataAce</span>
        </div>

        <div className="sidebar-section">
          <label className="section-label">File</label>
          <button className="upload-btn" onClick={() => fileInputRef.current.click()} disabled={uploading}>
            {uploading ? "Uploading..." : session ? "↑ Replace file" : "↑ Upload file"}
          </button>
          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls,.json"
            onChange={handleUpload} style={{ display: "none" }} />
          {session && (
            <div className="file-info">
              <span className="file-name">{session.filename}</span>
              <span className="file-meta">{session.rows.toLocaleString()} rows · {session.columns} cols</span>
            </div>
          )}
        </div>

        {session && (
          <div className="sidebar-section">
            <label className="section-label">History</label>
            <div className="undo-redo">
              <button onClick={handleUndo} disabled={!canUndo} className="icon-btn">↩ Undo</button>
              <button onClick={handleRedo} disabled={!canRedo} className="icon-btn">↪ Redo</button>
            </div>
            {history.length > 0 ? (
              <ol className="op-history">
                {history.map((op, i) => <li key={i} className="op-item">{op}</li>)}
              </ol>
            ) : (
              <p className="empty-hint">No operations yet</p>
            )}
          </div>
        )}

        {downloadReady && (
          <div className="sidebar-section">
            <label className="section-label">Export</label>
            <button className="download-btn" onClick={handleDownload}>↓ Cleaned file</button>
            <button className="download-btn secondary" onClick={handleNotebook}>↓ Jupyter notebook</button>
          </div>
        )}
      </aside>

      {/* ── Chat ── */}
      <main className="chat-area">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty-state">
              <span className="empty-icon">⬡</span>
              <p>Upload a file to get started</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-bubble">
                {msg.text.split("\n").map((line, j) => <span key={j}>{line}<br /></span>)}
              </div>
            </div>
          ))}
          {loading && (
            <div className="message assistant">
              <div className="message-bubble loading"><span /><span /><span /></div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="input-row">
          <input
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={session ? "Describe what to clean..." : "Upload a file first"}
            disabled={!session || loading}
          />
          <button className="send-btn" onClick={handleSend}
            disabled={!session || loading || !input.trim()}>→</button>
        </div>
      </main>

      {/* ── Resize Handle ── */}
      <div className="resize-handle" onMouseDown={onMouseDown}>
        <div className="resize-dots"><span /><span /><span /></div>
      </div>

      {/* ── Preview Panel ── */}
      <aside className="preview-panel">
        <div className="panel-header">
          <span className="section-label">Preview</span>
          {columns.length > 0 && (
            <span className="preview-meta">
              {totalRows.toLocaleString()} rows · {rows.length} loaded
            </span>
          )}
        </div>

        {columns.length > 0 ? (
          <div className="table-wrap" ref={tableWrapRef} onScroll={onTableScroll}>
            <table className="data-table">
              <thead>
                <tr>{columns.map((col) => <th key={col}>{col}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {columns.map((col) => (
                      <td key={col} className={row[col] === null ? "null-cell" : ""}>
                        {row[col] === null
                          ? <span className="null-badge">null</span>
                          : String(row[col])}
                      </td>
                    ))}
                  </tr>
                ))}
                {loadingMore && (
                  <tr>
                    <td colSpan={columns.length} className="loading-more">
                      Loading...
                    </td>
                  </tr>
                )}
                {!hasMore && rows.length > 0 && (
                  <tr>
                    <td colSpan={columns.length} className="end-of-data">
                      — {totalRows.toLocaleString()} rows total —
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state small"><p>No data loaded</p></div>
        )}
      </aside>
    </div>
  );
}