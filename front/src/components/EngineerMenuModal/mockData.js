export const engineers = {
    'ENG-104': {
        id: 'ENG-104',
        name: 'Иван Петров',
        role: 'Инженер-монтажник • Автомобиль',
        avatar: '👨‍🔧',
        shift: 'На смене (08:00 – 17:00)',
        location: 'Тверская ул. (в пути)',
        birthDate: '14.02.1995',
        skills: 'Установка роутеров, Монтаж ВОЛС, Настройка Wi-Fi 6',
        phone: '+7 912 345 67 89',
        transport: 'Автомобиль',
        requests: [
            { id: '8921', address: 'Тверская 12', status: 'green', statusText: 'В процессе (ETA 09:40)', active: true },
            { id: '8925', address: 'Лесная 4', status: 'gray', statusText: 'Ожидает (13:00 - 15:00)' },
            { id: '8930', address: 'Арбат 18', status: 'gray', statusText: 'Ожидает (15:30 - 17:00)' },
        ],
    },
    'ENG-102': {
        id: 'ENG-102',
        name: 'Алексей Смирнов',
        role: 'Инженер-монтажник • Пеший',
        avatar: '👨‍🔧',
        shift: 'На смене (09:00 – 18:00)',
        location: 'Ленинский пр. (на объекте)',
        birthDate: '30.06.2003',
        skills: 'Установка роутеров, Протяжка оптоволокна, Установка ТВ-приставок',
        phone: '+7 634 912 38 74',
        transport: 'Автомобиль',
        requests: [
            { id: '8922', address: 'Ленинский пр. 45', status: 'green', statusText: 'В процессе (ETA 11:20)', active: true },
            { id: '8926', address: 'Парковая 3', status: 'gray', statusText: 'Ожидает (14:00 - 16:00)' },
        ],
    },
}

export const trunkEquipment = [
    {
        title: 'Router Beeline Wi-Fi 6 Pro',
        sn: 'S/N: 9842-AAAA-8812',
        condition: 'Новое',
        qty: '1 шт',
    },
    {
        title: 'ONT-терминал Huawei HG8120H',
        sn: 'S/N: HW-7721-0092-X',
        condition: 'Новое',
        qty: '2 шт',
    },
]

