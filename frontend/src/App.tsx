import { Routes, Route } from 'react-router-dom'
import { Landing } from '@/routes/Landing'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
    </Routes>
  )
}
