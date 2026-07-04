import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'

const STATUS_LABEL = {
  pending: '等待中',
  generating: '生成中',
  done: '已完成',
  failed: '失败',
}

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABEL[status] || status}</span>
}

export default function DishDetail() {
  const { id } = useParams()
  const [dish, setDish] = useState(null)
  const [videosMap, setVideosMap] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [generating, setGenerating] = useState(false)
  const [expandedId, setExpandedId] = useState(null)
  const videosMapRef = useRef(videosMap)

  videosMapRef.current = videosMap

  const loadVideos = useCallback(async (promptIds) => {
    const map = {}
    await Promise.all(
      promptIds.map(async (pid) => {
        try {
          map[pid] = await api.listVideos(pid)
        } catch {
          map[pid] = []
        }
      })
    )
    setVideosMap(map)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getDish(id)
      setDish(data)
      await loadVideos(data.prompt_versions.map((p) => p.id))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [id, loadVideos])

  useEffect(() => { load() }, [load])

  // 轮询进行中的视频（仅 GET 查状态，不会重复触发生成）
  useEffect(() => {
    const timer = setInterval(async () => {
      const map = videosMapRef.current
      const pending = Object.values(map).flat().filter(
        (v) => v.status === 'pending' || v.status === 'generating',
      )
      if (pending.length === 0) return

      let nextMap = null
      for (const v of pending) {
        try {
          const updated = await api.getVideo(v.id)
          const pid = updated.prompt_version_id
          const prev = (nextMap || map)[pid] || []
          const old = prev.find((item) => item.id === updated.id)
          if (!old || old.status !== updated.status || old.video_url !== updated.video_url) {
            if (!nextMap) nextMap = { ...map }
            nextMap[pid] = prev.map((item) => (item.id === updated.id ? updated : item))
          }
        } catch {
          // 已删除的记录从列表移除
          if (!nextMap) nextMap = { ...map }
          for (const [pid, list] of Object.entries(nextMap)) {
            nextMap[pid] = list.filter((item) => item.id !== v.id)
          }
        }
      }
      if (nextMap) setVideosMap(nextMap)
    }, 8000)

    return () => clearInterval(timer)
  }, [id])

  const handleGeneratePrompt = async () => {
    setGenerating(true)
    setError('')
    try {
      await api.generatePrompt(id)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleDeletePrompt = async (promptId) => {
    if (!confirm('确定删除此提示词版本及关联视频？')) return
    try {
      await api.deletePrompt(promptId)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const handleGenerateVideo = async (promptId) => {
    setError('')
    const hasActive = (videosMap[promptId] || []).some(
      (v) => v.status === 'pending' || v.status === 'generating',
    )
    if (hasActive) {
      setError('该提示词已有视频在生成中，请等待完成或先删除')
      return
    }
    try {
      const video = await api.createVideo(promptId)
      setVideosMap((prev) => ({
        ...prev,
        [promptId]: [video, ...(prev[promptId] || [])],
      }))
    } catch (e) {
      setError(e.message)
    }
  }

  const handleDeleteVideo = async (promptId, videoId, status) => {
    const msg = (status === 'pending' || status === 'generating')
      ? '该视频正在生成中，确定删除？\n（排队任务会尝试取消；已在生成的任务可能仍会计费）'
      : '确定删除此视频记录？'
    if (!confirm(msg)) return
    try {
      await api.deleteVideo(videoId)
      setVideosMap((prev) => ({
        ...prev,
        [promptId]: (prev[promptId] || []).filter((v) => v.id !== videoId),
      }))
    } catch (e) {
      setError(e.message)
    }
  }

  const copyText = (text) => {
    navigator.clipboard.writeText(text)
    alert('已复制到剪贴板')
  }

  if (loading) return <p className="loading">加载中…</p>
  if (!dish) return <p className="error">菜品不存在</p>

  return (
    <div>
      <p><Link to="/">← 返回列表</Link></p>

      <div className="card">
        <h2 style={{ margin: '0 0 8px' }}>{dish.name}</h2>
        <p className="meta">{dish.category || '—'} · {dish.region || '—'}</p>
        <button
          className="btn btn-primary"
          onClick={handleGeneratePrompt}
          disabled={generating}
        >
          {generating ? '千问生成中…' : '生成提示词'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {dish.publish_copy && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>发布的文案</h3>
            <button className="btn btn-secondary" onClick={() => copyText(dish.publish_copy)}>
              复制
            </button>
          </div>
          <div className="copy-box" style={{ marginTop: 12 }}>{dish.publish_copy}</div>
        </div>
      )}

      <div className="card">
        <h3 style={{ margin: '0 0 16px' }}>提示词版本 ({dish.prompt_versions.length})</h3>
        {dish.prompt_versions.length === 0 && (
          <p style={{ color: '#999' }}>暂无提示词，点击上方按钮生成</p>
        )}
        {dish.prompt_versions.map((p) => (
          <div key={p.id} style={{ borderTop: '1px solid #eee', paddingTop: 16, marginTop: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
              <div>
                <strong>版本 {p.version_no}</strong>
                <span className="meta" style={{ marginLeft: 12 }}>
                  {new Date(p.created_at).toLocaleString('zh-CN')}
                </span>
              </div>
              <div>
                <button className="btn btn-secondary" onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}>
                  {expandedId === p.id ? '收起' : '展开'}
                </button>
                <button className="btn btn-success" onClick={() => handleGenerateVideo(p.id)}>
                  生成视频
                </button>
                <button className="btn btn-danger" onClick={() => handleDeletePrompt(p.id)}>
                  删除
                </button>
              </div>
            </div>

            {expandedId === p.id && (
              <div style={{ marginTop: 12 }}>
                <p><strong>正向提示词</strong></p>
                <div className="prompt-box">{p.content}</div>
                {p.negative_prompt && (
                  <>
                    <p style={{ marginTop: 12 }}><strong>反向提示词</strong></p>
                    <div className="prompt-box">{p.negative_prompt}</div>
                  </>
                )}
                <button className="btn btn-secondary" style={{ marginTop: 8 }} onClick={() => copyText(p.content + (p.negative_prompt ? '\n\n反向提示词\n' + p.negative_prompt : ''))}>
                  复制提示词
                </button>
              </div>
            )}

            {(videosMap[p.id] || []).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong>视频</strong>
                {(videosMap[p.id] || []).map((v) => (
                  <div key={v.id} style={{ marginTop: 8, padding: 12, background: '#f9fafb', borderRadius: 8 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
                      <StatusBadge status={v.status} />
                      <span className="meta">{new Date(v.created_at).toLocaleString('zh-CN')}</span>
                      <button className="btn btn-danger" style={{ marginLeft: 'auto' }} onClick={() => handleDeleteVideo(p.id, v.id, v.status)}>
                        删除
                      </button>
                    </div>
                    {v.error_msg && <p style={{ color: '#991b1b', fontSize: 13 }}>{v.error_msg}</p>}
                    {v.video_url && (
                      <video src={v.video_url} controls style={{ maxHeight: 400 }} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
