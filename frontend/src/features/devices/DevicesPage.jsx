import { useEffect, useState } from 'react'
import { getDevices } from '../../api/client'
import useStore from '../../store/useStore'
import { Card, Pill, EmptyState, Button, useToast } from '../../ui'
import './DevicesPage.css'

const TYPE_META = {
  light:   { icon: '💡', label: 'Đèn',     accent: 'warn'    },
  switch:  { icon: '⚡', label: 'Công tắc', accent: 'info'    },
  lock:    { icon: '🔒', label: 'Khoá',    accent: 'success' },
  climate: { icon: '❄️', label: 'Điều hoà', accent: 'info'   },
  sensor:  { icon: '🌡', label: 'Cảm biến', accent: 'neutral' },
  default: { icon: '📦', label: 'Thiết bị', accent: 'neutral' },
}

export default function DevicesPage() {
  const devices = useStore(s => s.devices)
  const setDevices = useStore(s => s.setDevices)
  const setPage = useStore(s => s.setPage)
  const addMessage = useStore(s => s.addMessage)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const toast = useToast()

  useEffect(() => {
    let alive = true
    getDevices()
      .then((list) => { if (alive) { setDevices(list); setError(null) } })
      .catch((e) => { if (alive) setError(e?.message || 'Không tải được thiết bị') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const tapDevice = (dev) => {
    setPage('chat')
    addMessage({
      id: Date.now() + '-quick',
      role: 'user',
      text: `Kiểm tra ${dev.friendly_name}`,
      time: new Date().toISOString(),
    })
    toast.info(`Đã chuyển sang chat — hỏi về ${dev.friendly_name}`)
  }

  return (
    <div className="devices-page fade-in-up">
      <header className="devices-page__head">
        <div>
          <h2 className="devices-page__title">Thiết bị</h2>
          <p className="devices-page__sub">
            {devices.length > 0
              ? `${devices.length} thiết bị đã kết nối`
              : 'Chưa có thiết bị nào'}
          </p>
        </div>
      </header>

      {loading && (
        <div className="devices-page__skeleton">
          {[0,1,2,3].map((i) => (
            <div key={i} className="device-skeleton" aria-hidden />
          ))}
        </div>
      )}

      {!loading && error && (
        <EmptyState
          title="Không tải được danh sách thiết bị"
          description={error}
          action={
            <Button variant="secondary" onClick={() => window.location.reload()}>
              Thử lại
            </Button>
          }
        />
      )}

      {!loading && !error && devices.length === 0 && (
        <EmptyState
          title="Chưa có thiết bị nào"
          description="Aisha sẽ tự động phát hiện khi bạn cấu hình Home Assistant ở backend."
        />
      )}

      {!loading && !error && devices.length > 0 && (
        <div className="devices-grid">
          {devices.map((d) => {
            const meta = TYPE_META[d.device_type] || TYPE_META.default
            return (
              <Card
                key={d.entity_id}
                variant="glass"
                interactive
                onClick={() => tapDevice(d)}
                className="device-card"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') tapDevice(d) }}
                aria-label={`Mở chat hỏi về ${d.friendly_name}`}
              >
                <div className={`device-card__icon device-card__icon--${d.device_type || 'default'}`}>
                  {meta.icon}
                </div>
                <div className="device-card__name">{d.friendly_name}</div>
                <div className="device-card__entity">{d.entity_id}</div>
                <div className="device-card__footer">
                  <Pill tone={meta.accent} size="sm">{meta.label}</Pill>
                  <Pill tone="success" size="sm" dot>Sẵn sàng</Pill>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
