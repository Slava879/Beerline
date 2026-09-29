export const masters = [
    { id: 'ENG-104', name: 'Иван Петров', mode: 'Авто', shift: '08:00–17:00', requests: 3, online: true },
    { id: 'ENG-102', name: 'Алексей Смирнов', mode: 'Пеший', shift: '09:00–18:00', requests: 2, online: false },
]

export const stats = { online: '2 / 2 чел.', mileage: '32.4 км', mileageDelta: '-15%' }

export const replanningEvents = [
    {
        id: 'EVT-1', requestId: 'REQ-105', time: '10:42:05',
        title: 'Срочная заявка #REQ-105',
        description: 'Адрес: ул. Ленина 45 | Подключение XGS-PON',
        reason: 'Причина: Требуется автоматический перерасчет',
        engineerId: null,
    },
    {
        id: 'EVT-2', requestId: 'REQ-104', time: '10:42:05',
        title: 'Недоступность инженера (#ENG-102)',
        description: 'Сход с линии по поломке авто',
        reason: '3 заявки под угрозой',
        engineerId: 'ENG-102',
    },
]

export const unallocatedRequests = [
    {
        id: '8921', date: '8 сентября 2026', window: '09:00 — 12:00',
        address: 'Тверская 12', service: 'Подключение интернета',
        suggested: { name: 'Иван Петров', info: '(Оптимален, +2.1 км)' },
    },
]

export const distributedRequests = [
    { id: '8922', description: '8 сентября (12:00–15:00) | Ленинский пр. 45', status: 'В очереди' },
    { id: '8923', description: '8 сентября (15:30–17:00) | Арбат 18', status: 'В пути' },
]
// Шаблоны для входящих заявок (симуляция прихода из апплета)
export const incomingRequestTemplates = [
    { priority: 'urgent', service: 'Аварийное восстановление интернета' },
    { priority: 'urgent', service: 'Прерывание ТВ-сигнала' },
    { priority: 'normal', service: 'Подключение интернета и ТВ' },
    { priority: 'normal', service: 'Диагностика линии' },
    { priority: 'normal', service: 'Замена оборудования' },
]

export const incomingAddresses = [
    'ул. Тверская 12', 'Ленинский пр. 45', 'ул. Арбат 18', 'пр. Мира 7',
    'ул. Гагарина 3', 'Кутузовский пр. 21', 'ул. Садовая 5', 'Никольская 10',
]
