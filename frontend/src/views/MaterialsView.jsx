import ImportFromUrlPanel from '../ImportFromUrlPanel.jsx'

export default function MaterialsView({
  materials,
  message,
  query,
  form,
  onQueryChange,
  onSearch,
  onFormChange,
  onCreate,
  onOpenMaterial,
  onImported,
  onMessage,
}) {
  return <section className="module">
    <div className="section-heading light"><div><p className="eyebrow">声音训练素材</p><h2>导入并进入训练</h2></div></div>
    <ImportFromUrlPanel onImported={onImported} onMessage={onMessage} />
    {message && <p className="notice">{message}</p>}
    <div className="section-heading light"><div><p className="eyebrow">我的素材</p><h2>搜索并进入训练</h2></div></div>
    <form className="search-bar" onSubmit={onSearch}><input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="搜索标题、编号或 transcript" /><button className="primary" type="submit">搜索</button></form><p className="search-hint">当前搜索范围：本地已导入素材；外部素材源将在 MaterialProvider 接入后开放。</p>
    <details className="import-manual">
      <summary>高级：手动录入素材（需要自备音频文件和逐行文稿）</summary>
      <form className="import-form" onSubmit={onCreate}><input required placeholder="素材 ID，如 lesson-001" value={form.material_id} onChange={(event) => onFormChange({ ...form, material_id: event.target.value })} /><input required placeholder="素材标题" value={form.title} onChange={(event) => onFormChange({ ...form, title: event.target.value })} /><input required placeholder="音频路径（本地文件）" value={form.audio_path} onChange={(event) => onFormChange({ ...form, audio_path: event.target.value })} /><textarea required placeholder="每行一句，至少 3 行" value={form.transcript} onChange={(event) => onFormChange({ ...form, transcript: event.target.value })} /><button className="primary" type="submit">保存并进入训练</button></form>
    </details>
    <div className="result-list">{materials.length ? materials.map((material) => <button className="result-row" key={material.material_id} onClick={() => onOpenMaterial(material.material_id)}><div><strong>{material.title}</strong><p>{material.material_id} · {Math.round(material.duration_seconds)} 秒</p></div><span>{material.current_state || material.status} →</span></button>) : <p className="empty light-text">没有匹配素材。可以用上面的视频链接提取一篇。</p>}</div>
  </section>
}
