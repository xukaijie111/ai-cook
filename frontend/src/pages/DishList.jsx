import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function DishList() {
  const [dishes, setDishes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [seeding, setSeeding] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setDishes(await api.listDishes())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleSeed = async () => {
    if (!confirm('调用千问生成 50 道火爆菜品并入库？已存在的会跳过。')) return
    setSeeding(true)
    setError('')
    try {
      const result = await api.seedDishes()
      alert(`完成：新增 ${result.created} 道，跳过 ${result.skipped} 道`)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSeeding(false)
    }
  }

  const handleDelete = async (id, name) => {
    if (!confirm(`确定删除「${name}」及其所有提示词和视频？`)) return
    try {
      await api.deleteDish(id)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const filtered = dishes.filter((d) =>
    d.name.includes(search) ||
    (d.category || '').includes(search) ||
    (d.region || '').includes(search)
  )

  return (
    <div>
      <div className="toolbar">
        <button className="btn btn-primary" onClick={handleSeed} disabled={seeding}>
          {seeding ? '生成中…' : '生成 50 道火爆菜'}
        </button>
        <input
          className="search-input"
          placeholder="搜索菜名、菜系、地区…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {error && <div className="error">{error}</div>}

      <div className="card">
        {loading ? (
          <p className="loading">加载中…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>菜名</th>
                <th>菜系</th>
                <th>地区</th>
                <th>提示词版本</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <tr key={d.id}>
                  <td><Link to={`/dishes/${d.id}`}>{d.name}</Link></td>
                  <td>{d.category || '—'}</td>
                  <td>{d.region || '—'}</td>
                  <td>{d.prompt_count}</td>
                  <td>
                    <Link to={`/dishes/${d.id}`} className="btn btn-secondary" style={{ textDecoration: 'none' }}>
                      详情
                    </Link>
                    <button className="btn btn-danger" onClick={() => handleDelete(d.id, d.name)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#999' }}>暂无菜品</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
