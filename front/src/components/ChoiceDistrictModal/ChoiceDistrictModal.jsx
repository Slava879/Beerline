import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
    getDistricts, getDistrict, patchDistrict,
    uploadCsv, deleteDistrictData,
} from '../../api/districts'
import './ChoiceDistrictModal.css'

const EMPTY_FORM = { city: '', street: '', house: '', building: '' }

const ChoiceDistrictModal = ({ isOpen, onClose, onSelect, selectedId }) => {
    const [districts, setDistricts] = useState([])
    const [loading, setLoading]     = useState(false)
    const [loadError, setLoadError] = useState(null)

    const [district, setDistrict] = useState(null)
    const [isOpenList, setIsOpenList] = useState(false)

    const [form, setForm] = useState(EMPTY_FORM)
    const [saving, setSaving]     = useState(false)
    const [saveInfo, setSaveInfo] = useState(null)

    const [isDeleteOpen,  setIsDeleteOpen]  = useState(false)
    const [isConfirmOpen, setIsConfirmOpen] = useState(false)
    const [deletePeriod,  setDeletePeriod]  = useState([])
    const [isDeleting,    setIsDeleting]    = useState(false)

    const [isUploading, setIsUploading] = useState(false)
    const [uploadInfo, setUploadInfo]   = useState(null)
    const fileInputRef = useRef(null)

    // Функция перезагрузки списка районов (переиспользуется)
    const loadDistricts = async () => {
        setLoading(true); setLoadError(null)
        try {
            const data = await getDistricts()
            setDistricts(data.districts ?? [])
            return data.districts ?? []
        } catch (e) {
            setLoadError(e.message)
            return []
        } finally {
            setLoading(false)
        }
    }

    // Загрузка районов при открытии
    useEffect(() => {
        if (!isOpen) return
        let cancelled = false
        ;(async () => {
            if (cancelled) return
            await loadDistricts()
        })()
        return () => { cancelled = true }
    }, [isOpen])

    // Подхват ранее выбранного
    useEffect(() => {
        if (!isOpen || !selectedId || districts.length === 0) return
        const found = districts.find((d) => d.id === selectedId)
        if (found) setDistrict(found)
    }, [isOpen, selectedId, districts])

    // Когда выбран район — тянем его адрес
    useEffect(() => {
        if (!district?.id) { setForm(EMPTY_FORM); return }
        let cancelled = false
        getDistrict(district.id)
            .then((d) => {
                if (cancelled) return
                setForm({
                    city:     d.city     ?? '',
                    street:   d.street   ?? '',
                    house:    d.house    ?? '',
                    building: d.building ?? '',
                })
            })
            .catch((e) => { if (!cancelled) setSaveInfo({ type: 'error', text: e.message }) })
        return () => { cancelled = true }
    }, [district?.id])

    // Сброс при закрытии
    useEffect(() => {
        if (isOpen) return
        setDistrict(null)
        setForm(EMPTY_FORM)
        setSaveInfo(null); setUploadInfo(null)
        setIsDeleteOpen(false); setIsConfirmOpen(false)
        setDeletePeriod([]); setIsOpenList(false)
    }, [isOpen])

    if (!isOpen) return null

    const setField = (k, v) => setForm((prev) => ({ ...prev, [k]: v }))

    const handleSave = async () => {
        if (!district?.id) return
        setSaving(true); setSaveInfo(null)
        try {
            const updated = await patchDistrict(district.id, form)
            setDistricts((prev) => prev.map((d) =>
                d.id === updated.id ? { ...d, ...updated } : d))
            setDistrict((prev) => ({ ...prev, ...updated }))
            setSaveInfo({ type: 'ok', text: 'Адрес сохранён' })
        } catch (e) {
            setSaveInfo({ type: 'error', text: e.message })
        } finally {
            setSaving(false)
        }
    }

    const openDistrict = () => {
        if (!district) return
        onSelect?.(district)
        onClose()
    }

    // CSV
    const pickFile = () => {
        if (isUploading) return
        setUploadInfo(null)
        fileInputRef.current?.click()
    }

    const onFileChosen = async (e) => {
        const file = e.target.files?.[0]
        e.target.value = ''
        if (!file) return
        if (!/\.csv$/i.test(file.name) && file.type !== 'text/csv') {
            setUploadInfo({ type: 'error', text: 'Можно загрузить только CSV-файл' })
            return
        }
        setIsUploading(true)
        setUploadInfo({ type: 'ok', text: 'Отправка файла…' })
        try {
            const res = await uploadCsv(file)
            const n = typeof res?.imported === 'number' ? ` (строк: ${res.imported})` : ''
            setUploadInfo({ type: 'ok', text: `Файл «${file.name}» успешно загружен${n}` })

            // >>> ПОСЛЕ ЗАГРУЗКИ ОБНОВЛЯЕМ СПИСОК РАЙОНОВ
            // Бэк мог создать новый район по имени файла.
            const refreshed = await loadDistricts()

            // Если район с таким же именем (имя файла без .csv) уже был выбран — обновим его данные
            const fileBase = file.name.replace(/\.[^.]+$/, '').trim()
            const created = refreshed.find(
                (d) => d.name.toLowerCase() === fileBase.toLowerCase()
            )
            if (created) {
                // автоматически подставляем в селект как выбранный
                setDistrict(created)
            }
        } catch (err) {
            setUploadInfo({ type: 'error', text: `Не удалось загрузить: ${err.message}` })
        } finally {
            setIsUploading(false)
        }
    }

    // Удаление
    const togglePeriod = (v) => setDeletePeriod((prev) =>
        prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v])

    const confirmDelete = async () => {
        if (!district?.id) return
        setIsDeleting(true)
        try {
            await deleteDistrictData(district.id, deletePeriod)
            setIsConfirmOpen(false); setIsDeleteOpen(false)
            setDeletePeriod([]); onClose()
        } catch (e) {
            setSaveInfo({ type: 'error', text: `Ошибка удаления: ${e.message}` })
        } finally {
            setIsDeleting(false)
        }
    }

    return createPortal(
        <main className="cdm__page" onClick={onClose}>
            <section className="cdm" onClick={(e) => e.stopPropagation()}>

                <header className="cdm__header">
                    <div>
                        <h2 className="cdm__title">Выбор участка</h2>
                        <p className="cdm__subtitle">
                            Настройте адрес офиса и загрузите данные по району
                        </p>
                    </div>
                    <button className="cdm__close" type="button"
                        onClick={onClose} aria-label="Закрыть">
                        <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true">
                            <path d="M1.08 15.36 0 14.28 6.56 7.68 0 1.08 1.08 0 7.64 6.6 14.16 0l1.08 1.08L8.68 7.68l6.56 6.6-1.08 1.08L7.64 8.8 1.08 15.36Z" fill="#94A3B8"/>
                        </svg>
                    </button>
                </header>

                {/* Список участков */}
                <div className="cdm__section">
                    <div className="cdm__section-label">Участок</div>
                    <div className="cdm__select-wrap">
                        <button
                            className={
                                'cdm__select' +
                                (isOpenList ? ' cdm__select--open' : '')
                            }
                            type="button"
                            onClick={() => setIsOpenList((v) => !v)}>
                            <span className="cdm__select-value">
                                {district?.name || 'Выберите участок'}
                            </span>
                            <span className={
                                'cdm__chevron' +
                                (isOpenList ? ' cdm__chevron--open' : '')
                            } />
                        </button>

                        {isOpenList && (
                            <div className="cdm__options">
                                {loading && <div className="cdm__option">Загрузка…</div>}
                                {loadError && (
                                    <div className="cdm__option cdm__option--error">
                                        {loadError}
                                    </div>
                                )}
                                {!loading && !loadError && districts.length === 0 && (
                                    <div className="cdm__option">Районов нет</div>
                                )}
                                {!loading && !loadError && districts.map((d) => (
                                    <button key={d.id} type="button"
                                        className={
                                            'cdm__option' +
                                            (district?.id === d.id ? ' cdm__option--active' : '')
                                        }
                                        onClick={() => { setDistrict(d); setIsOpenList(false) }}>
                                        <span>{d.name}</span>
                                        {typeof d.requestsCount === 'number' && (
                                            <span className="cdm__option-count">
                                                {d.requestsCount}
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Адрес офиса */}
                {district && (
                    <div className="cdm__section cdm__section--address">
                        <div className="cdm__section-label">Адрес офиса участка</div>

                        <div className="cdm__grid">
                            <label className="cdm__field">
                                <span className="cdm__field-label">Город</span>
                                <input className="cdm__input" value={form.city}
                                    onChange={(e) => setField('city', e.target.value)}
                                    placeholder="Москва" />
                            </label>

                            <label className="cdm__field cdm__field--wide">
                                <span className="cdm__field-label">Улица</span>
                                <input className="cdm__input" value={form.street}
                                    onChange={(e) => setField('street', e.target.value)}
                                    placeholder="ул. Юных Ленинцев" />
                            </label>

                            <label className="cdm__field">
                                <span className="cdm__field-label">Дом</span>
                                <input className="cdm__input" value={form.house}
                                    onChange={(e) => setField('house', e.target.value)}
                                    placeholder="83" />
                            </label>

                            <label className="cdm__field">
                                <span className="cdm__field-label">Корпус</span>
                                <input className="cdm__input" value={form.building}
                                    onChange={(e) => setField('building', e.target.value)}
                                    placeholder="4" />
                            </label>
                        </div>

                        <button className="cdm__btn cdm__btn--save" type="button"
                            onClick={handleSave} disabled={saving}>
                            {saving ? 'Сохранение…' : 'Сохранить изменения'}
                        </button>

                        {saveInfo && (
                            <div className={`cdm__notice cdm__notice--${saveInfo.type}`}>
                                {saveInfo.text}
                            </div>
                        )}
                    </div>
                )}

                <input ref={fileInputRef} type="file" accept=".csv,text/csv"
                    style={{ display: 'none' }} onChange={onFileChosen} />

                {uploadInfo && (
                    <div className={`cdm__notice cdm__notice--${uploadInfo.type}`}>
                        {uploadInfo.text}
                    </div>
                )}

                <footer className="cdm__footer">
                    <button className="cdm__btn cdm__btn--yellow" type="button"
                        disabled={isUploading} onClick={pickFile}>
                        {isUploading ? 'Отправка…' : 'Загрузить CSV'}
                    </button>

                    <button className="cdm__btn cdm__btn--green" type="button"
                        disabled={!district} onClick={openDistrict}>
                        Открыть данные по району
                    </button>

                    <button className="cdm__btn cdm__btn--ghost" type="button"
                        onClick={() => setIsDeleteOpen(true)}>
                        Удаление данных
                    </button>
                </footer>
            </section>

            {/* Панель удаления */}
            {isDeleteOpen && (
                <div className="cdm__overlay" onClick={(e) => e.stopPropagation()}>
                    <div className="cdm__dialog">
                        <div className="cdm__dialog-title">Удаление данных по району</div>
                        <p className="cdm__dialog-text">
                            Выберите период, за который нужно удалить данные.
                        </p>
                        <label className="cdm__checkbox">
                            <input type="checkbox"
                                checked={deletePeriod.includes('today')}
                                onChange={() => togglePeriod('today')} />
                            <span>Сегодня</span>
                        </label>
                        <label className="cdm__checkbox">
                            <input type="checkbox"
                                checked={deletePeriod.includes('previous')}
                                onChange={() => togglePeriod('previous')} />
                            <span>Предыдущие дни</span>
                        </label>

                        <div className="cdm__dialog-actions">
                            <button className="cdm__btn cdm__btn--red" type="button"
                                disabled={!district || deletePeriod.length === 0}
                                onClick={() => { setIsDeleteOpen(false); setIsConfirmOpen(true) }}>
                                Удалить
                            </button>
                            <button className="cdm__btn cdm__btn--ghost" type="button"
                                onClick={() => setIsDeleteOpen(false)}>
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {isConfirmOpen && (
                <div className="cdm__overlay" onClick={(e) => e.stopPropagation()}>
                    <div className="cdm__dialog">
                        <div className="cdm__dialog-title">Подтверждение</div>
                        <p className="cdm__dialog-text">
                            Вы уверены, что хотите удалить данные?
                        </p>
                        <div className="cdm__dialog-actions">
                            <button className="cdm__btn cdm__btn--red" type="button"
                                disabled={isDeleting} onClick={confirmDelete}>
                                {isDeleting ? 'Удаление…' : 'Удалить'}
                            </button>
                            <button className="cdm__btn cdm__btn--ghost" type="button"
                                onClick={() => setIsConfirmOpen(false)}>
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </main>,
        document.body,
    )
}

export default ChoiceDistrictModal