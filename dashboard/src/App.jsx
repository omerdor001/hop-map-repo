import { useState, useEffect } from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import Sidebar from "./components/Sidebar"
import Homepage from "./components/Homepage"
import Kids from "./components/Kids"

export default function App() {
  const [activeId, setActiveId]   = useState(null)
  const [childList, setChildList] = useState([])

  useEffect(() => {
    fetch("/api/children")
      .then(r => r.json())
      .then(data => {
        const list = data.children || []
        setChildList(list)
        if (list.length > 0) setActiveId(list[0].childId)
      })
      .catch(() => {})
  }, [])

  return (
    <BrowserRouter>
      <div style={{ display: "flex", minHeight: "100vh", background: "#0d0d0f" }}>
        <Sidebar />
        <div style={{ flex: 1 }}>
          <Routes>
            <Route path="/" element={<Homepage childList={childList} activeId={activeId} setActiveId={setActiveId} />} />
            <Route path="/kids" element={<Kids setChildList={setChildList} />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}