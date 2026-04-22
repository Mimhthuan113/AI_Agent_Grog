import { useEffect, useState } from 'react'
import { getAudit } from '../api/client'
import './HistoryPage.css'

export default function HistoryPage() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const data = await getAudit(50)
      setRecords(data.records || [])
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  return (
    <div className="history-page">
      <div className="history-header">
        <div>
          <h2 className="page-heading">Lịch sử lệnh</h2>
          <p className="page-sub">{records.length} bản ghi gần nhất</p>
        </div>
        <button className="refresh-btn" onClick={loadData}>🔄</button>
      </div>

      <div className="history-scroll">
        {loading && <p className="empty-text">Đang tải...</p>}
        {!loading && records.length === 0 && <p className="empty-text">Chưa có lịch sử</p>}

        {records.map((r, i) => {
          const approved = r.decision === 'APPROVED'
          return (
            <div key={i} className={`history-row glass ${approved ? 'approved' : 'denied'}`}>
              <div className={`history-dot ${approved ? 'ok' : 'fail'}`}>
                {approved ? '✅' : '🚫'}
              </div>
              <div className="history-info">
                <div className="history-cmd">{r.entity_id} → {r.action}</div>
                <div className="history-time">
                  {r.timestamp ? new Date(r.timestamp).toLocaleString('vi') : ''}
                  {r.deny_reason ? ` • ${r.deny_reason}` : ''}
                </div>
              </div>
              <span className={`history-badge ${approved ? 'ok' : 'fail'}`}>
                {r.decision}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
