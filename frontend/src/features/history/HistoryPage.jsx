import { useEffect, useState, useCallback } from 'react'
import { getAudit } from '../../api/client'
import { Button, Card, Pill, EmptyState, useToast } from '../../ui'
import { formatTime } from '../../lib/format'
import './HistoryPage.css'

export default function HistoryPage() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const toast = useToast()

  const loadData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const data = await getAudit(50)
      setRecords(data.records || [])
      setError(null)
      if (silent) toast.success('Đã làm mới')
    } catch (e) {
      setError(e?.message || 'Không tải được lịch sử')
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { loadData() }, [loadData])

  return (
    <div className="history-page fade-in-up">
      <header className="history-page__head">
        <div>
          <h2 className="history-page__title">Lịch sử lệnh</h2>
          <p className="history-page__sub">
            {records.length} bản ghi gần nhất
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => loadData(true)}
          iconLeft={<RefreshIcon />}
          aria-label="Làm mới"
        >
          Làm mới
        </Button>
      </header>

      {loading && (
        <div className="history-page__skeleton">
          {[0,1,2,3,4].map((i) => (
            <div key={i} className="history-skeleton" aria-hidden />
          ))}
        </div>
      )}

      {!loading && error && (
        <EmptyState
          title="Không tải được lịch sử"
          description={error}
          action={<Button variant="secondary" onClick={() => loadData()}>Thử lại</Button>}
        />
      )}

      {!loading && !error && records.length === 0 && (
        <EmptyState
          title="Chưa có lịch sử"
          description="Mọi lệnh bạn ra cho Aisha sẽ được ghi lại tại đây để bạn theo dõi."
        />
      )}

      {!loading && !error && records.length > 0 && (
        <div className="history-list">
          {records.map((r, i) => {
            const approved = r.decision === 'APPROVED'
            return (
              <Card key={i} variant="flat" className={`history-row ${approved ? 'is-ok' : 'is-fail'}`}>
                <div className={`history-row__icon ${approved ? 'is-ok' : 'is-fail'}`} aria-hidden>
                  {approved ? <CheckIcon /> : <BlockIcon />}
                </div>
                <div className="history-row__info">
                  <div className="history-row__cmd">
                    <span className="history-row__entity">{r.entity_id}</span>
                    <span className="history-row__sep">→</span>
                    <span className="history-row__action">{r.action}</span>
                  </div>
                  <div className="history-row__meta">
                    <span>{formatTime(r.timestamp)}</span>
                    {r.deny_reason && (
                      <>
                        <span className="history-row__dot">·</span>
                        <span className="history-row__reason">{r.deny_reason}</span>
                      </>
                    )}
                  </div>
                </div>
                <Pill tone={approved ? 'success' : 'danger'} size="sm">
                  {r.decision}
                </Pill>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10"/>
      <path d="M3 18a9 9 0 0 0 16-3"/>
      <polyline points="1 20 1 14 7 14"/>
      <path d="M21 6a9 9 0 0 0-16 3"/>
    </svg>
  )
}
function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
}
function BlockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
    </svg>
  )
}
