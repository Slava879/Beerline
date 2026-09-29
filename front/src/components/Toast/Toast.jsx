// frontend/src/components/Toast/Toast.jsx
import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import './Toast.css'

const ICONS = {
    success: '✓',
    error:   '✕',
    warning: '!',
    info:    'ℹ',
}

const ToastItem = ({ toast, onDismiss }) => {
    useEffect(() => {
        const t = setTimeout(() => onDismiss(toast.id), toast.duration ?? 3500)
        return () => clearTimeout(t)
    }, [toast.id, toast.duration, onDismiss])

    return (
        <div
            className={`toast toast--${toast.type || 'info'}`}
            onClick={() => onDismiss(toast.id)}
            role="status"
        >
            <span className="toast__icon">{ICONS[toast.type] || ICONS.info}</span>
            <span className="toast__text">{toast.text}</span>
        </div>
    )
}

const Toast = ({ toasts, onDismiss }) => {
    if (!toasts.length) return null
    return createPortal(
        <div className="toast-container">
            {toasts.map((t) => (
                <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
            ))}
        </div>,
        document.body,
    )
}

export default Toast