// Shared response handling.
//
// The API is served by the same FastAPI process as this bundle, but during
// development the Vite dev server proxies /api to port 8000. When that backend
// is down, or a request is cut short, the proxy answers with an EMPTY body.
// Calling response.json() on an empty body throws the cryptic
// "Unexpected end of JSON input", which tells the user nothing. readJson()
// turns every non-JSON/empty outcome into an actionable Chinese message while
// keeping the call sites' existing control flow (payload in, Error out).

export async function readJson(response) {
  let text = ''
  try {
    text = await response.text()
  } catch {
    throw new Error('读取服务响应失败：连接被中断，请确认后端仍在运行。')
  }

  if (!text.trim()) {
    if (response.ok) {
      throw new Error('服务返回了空响应，请确认后端仍在运行后重试。')
    }
    throw new Error(
      `请求失败（HTTP ${response.status}）：后端可能未启动、已崩溃或请求被中断。请确认后端服务正常后重试。`,
    )
  }

  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`服务返回了非 JSON 响应（HTTP ${response.status}），请查看后端日志确认原因。`)
  }
}

// Extracts the best available human-readable message from an error payload.
export function detailOf(payload, fallback) {
  const detail = payload?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message
  }
  return fallback
}
