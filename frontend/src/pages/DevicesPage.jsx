import { useEffect } from 'react'
import { getDevices } from '../api/client'
import useStore from '../store/useStore'
import './DevicesPage.css'

const ICONS = { light: '💡', switch: '⚡', lock: '🔒', climate: '❄️', sensor: '🌡' }

export default function DevicesPage() {
  const devices = useStore(s => s.devices)
  const setDevices = useStore(s => s.setDevices)
  const setPage = useStore(s => s.setPage)
  const addMessage = useStore(s => s.addMessage)

  useEffect(() => {
    getDevices().then(setDevices).catch(console.error)
  }, [])

  const tapDevice = (dev) => {
    setPage('chat')
    const store = useStore.getState()
    store.addMessage({
      id: Date.now() + '-quick',
      role: 'user',
      text: `Kiểm tra ${dev.friendly_name}`,
      time: new Date().toISOString(),
    })
  }

  return (
    <div className="devices-page">
      <h2 className="page-heading">Thiết bị</h2>
      <p className="page-sub">{devices.length} thiết bị đã đăng ký</p>
      <div className="dev-grid">
        {devices.map(d => (
          <div key={d.entity_id} className="dev-card glass" onClick={() => tapDevice(d)}>
            <div className={`dev-icon-wrap ${d.device_type}`}>
              {ICONS[d.device_type] || '📦'}
            </div>
            <div className="dev-name">{d.friendly_name}</div>
            <div className="dev-entity">{d.entity_id}</div>
            <div className="dev-chip">
              <span className="dev-dot" />
              Sẵn sàng
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
