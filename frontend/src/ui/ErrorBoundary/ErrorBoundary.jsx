import { Component } from 'react'
import './ErrorBoundary.css'

/**
 * ErrorBoundary — Catch lỗi runtime trong tree React, hiển thị fallback UI
 * thay vì để trang đen tinh.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    this.setState({ info })
    // eslint-disable-next-line no-console
    console.error('[Aisha:ErrorBoundary]', error, info)
  }

  handleReload = () => {
    this.setState({ error: null, info: null })
    window.location.reload()
  }

  handleClearStorage = () => {
    try {
      localStorage.clear()
      sessionStorage.clear()
    } catch (e) { /* ignore */ }
    window.location.reload()
  }

  render() {
    if (!this.state.error) return this.props.children

    const err = this.state.error
    const stack = this.state.info?.componentStack || err.stack || ''

    return (
      <div className="err-bound">
        <div className="err-bound__card">
          <div className="err-bound__orb" aria-hidden />
          <h1 className="err-bound__title">Có gì đó trục trặc</h1>
          <p className="err-bound__msg">{err.message || String(err)}</p>

          <details className="err-bound__details">
            <summary>Chi tiết kỹ thuật</summary>
            <pre className="err-bound__stack">{stack}</pre>
          </details>

          <div className="err-bound__actions">
            <button className="err-bound__btn err-bound__btn--primary" onClick={this.handleReload}>
              Tải lại trang
            </button>
            <button className="err-bound__btn err-bound__btn--ghost" onClick={this.handleClearStorage}>
              Xoá cache & đăng xuất
            </button>
          </div>
        </div>
      </div>
    )
  }
}
