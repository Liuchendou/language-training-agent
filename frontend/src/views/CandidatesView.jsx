import CandidatePanel from '../CandidatePanel.jsx'

export default function CandidatesView({ stage, message, onStageChange, onMessage, onImported }) {
  return <section className="module">
    <div className="section-heading light"><div><p className="eyebrow">候选素材</p><h2>自动获取素材</h2><p className="muted">从可访问的素材源搜索候选（默认 B站），选中后自动下载音频并生成逐句时间戳，可直接进入训练。</p></div></div>
    <CandidatePanel
      stage={stage}
      onStageChange={onStageChange}
      onMessage={onMessage}
      onPrepared={onImported}
    />
    {message && <p className="notice">{message}</p>}
  </section>
}
