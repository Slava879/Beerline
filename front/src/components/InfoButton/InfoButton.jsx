// frontend/src/components/InfoButton/InfoButton.jsx
import { useEffect, useRef, useState } from 'react'
import './InfoButton.css'

const InfoButton = ({ title, children, align = 'left' }) => {
    const [open, setOpen] = useState(false)
    const ref = useRef(null)

    useEffect(() => {
        if (!open) return
        const onClick = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false)
        }
        document.addEventListener('mousedown', onClick)
        return () => document.removeEventListener('mousedown', onClick)
    }, [open])

    return (
        <span className="info-btn" ref={ref}>
            <button
                type="button"
                className="info-btn__trigger"
                aria-label={title || 'Информация'}
                onClick={(e) => {
                    e.stopPropagation()
                    setOpen((v) => !v)
                }}
                onMouseEnter={() => setOpen(true)}
                onMouseLeave={() => setOpen(false)}
            >
                i
            </button>
            {open && (
                <div
                    className={`info-btn__popup info-btn__popup--${align}`}
                    onClick={(e) => e.stopPropagation()}
                >
                    {title && (
                        <div className="info-btn__title">{title}</div>
                    )}
                    <div className="info-btn__body">{children}</div>
                </div>
            )}
        </span>
    )
}

export default InfoButton