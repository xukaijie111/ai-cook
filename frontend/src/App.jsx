import { Routes, Route, Link } from 'react-router-dom'
import DishList from './pages/DishList'
import DishDetail from './pages/DishDetail'

export default function App() {
  return (
    <div className="container">
      <div className="header">
        <h1><Link to="/">做菜智能体 Admin</Link></h1>
      </div>
      <Routes>
        <Route path="/" element={<DishList />} />
        <Route path="/dishes/:id" element={<DishDetail />} />
      </Routes>
    </div>
  )
}
