// 训练视图。进度矩阵与状态机主体（progressMatrix / trainingBody）仍留在 App：
// 它们要读写 App 持有的训练状态与 API 回调，作为 render prop 传入可以让这次
// 拆分做到零逻辑改动（顺序依赖与闭包行为完全不变）。
export default function TrainingView({
  selected,
  message,
  progressMatrix,
  trainingBody,
  onSkip,
  onFirstListenEnd,
}) {
  return <section className="module training-module">
    {selected && <><div className="section-heading light"><div><p className="eyebrow">声音训练</p><h2>{selected.title}</h2><p className="muted">{selected.material_id} · {selected.sentences.length} 句 · {selected.source_name || '预置素材'}</p></div><div className="training-actions"><span className="state-badge">{selected.current_state}</span><button className="skip-btn" onClick={onSkip}>跳过此素材，换一篇</button></div></div>
    <div className="progress-matrix-wrap"><p className="eyebrow">流程状态</p>{progressMatrix()}</div>
    <div className="audio-panel"><p className="eyebrow">素材音频</p><audio controls preload="metadata" src={`/api/materials/${encodeURIComponent(selected.material_id)}/audio`} onEnded={() => onFirstListenEnd(true)} /><p className="muted">如果播放器提示找不到文件，请检查导入时填写的本地音频路径。</p></div>
    <div className="training-panel"><h3>继续训练</h3>{trainingBody()}</div>{message && <p className="notice">{message}</p>}</>}
  </section>
}
