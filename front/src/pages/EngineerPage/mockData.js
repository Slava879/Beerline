export const openRequest = {
    id: '8921', description: '8 сентября (09:00–12:00) | Тверская 12', status: 'В работе',
    date: '8 сентября 2026', window: '09:00 — 12:00',
    address: 'Тверская 12', service: 'Подключение интернета и ТВ',
    equipments: [
        { title: 'Роутер Wi-Fi 6 Pro (S/N: 984210)', qty: '1 шт' },
        { title: 'Приставка', qty: '2 шт' },
    ],
}

export const queuedRequests = [
    {
        id: '8922', description: '8 сентября (12:00–15:00) | Ленинский пр. 45', status: 'В очереди',
        date: '8 сентября 2026', window: '12:00 — 15:00', address: 'Ленинский пр. 45',
        service: 'Подключение интернета',
        equipments: [
            { title: 'Роутер Wi-Fi 6 Pro (S/N: 884501)', qty: '1 шт' },
            { title: 'Приставка', qty: '1 шт' },
        ],
    },
    {
        id: '8923', description: '8 сентября (15:30–17:00) | Арбат 18', status: 'В очереди',
        date: '8 сентября 2026', window: '15:30 — 17:00', address: 'Арбат 18',
        service: 'Диагностика линии',
        equipments: [
            { title: 'ONT-терминал Huawei HG8120H (S/N: HW-7721-0092-X)', qty: '1 шт' },
        ],
    },
]