import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function DishList() {
  const [dishes, setDishes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [seeding, setSeeding] = useState(false)
  const [customDish, setCustomDish] = useState('')
  const [adding, setAdding] = useState(false)
  const navigate = useNavigate()

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

  const handleAddCustom = async () => {
    const name = customDish.trim()
    if (!name) {
      setError('请输入菜名')
      return
    }
    setAdding(true)
    setError('')
    try {
      const dish = await api.createDish({ name })
      setCustomDish('')
      navigate(`/dishes/${dish.id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setAdding(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleAddCustom()
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
        <div className="custom-dish-input">
          <input
            className="search-input"
            placeholder="输入自定义菜名，回车添加…"
            value={customDish}
            onChange={(e) => setCustomDish(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button className="btn btn-secondary" onClick={handleAddCustom} disabled={adding}>
            {adding ? '添加中…' : '添加'}
          </button>
        </div>
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
