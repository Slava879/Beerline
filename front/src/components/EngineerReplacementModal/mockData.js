export const replacementCandidates = [
    {
        id: 'ENG-104', name: 'Иван Петров', available: true, recommended: true,
        dot: '#22C55E', nameColor: '#FFCC00', border: '1.5px solid #FFCC00',
        detailColor: '#FFCC00',
        details: [
            { icon: '🚗', text: 'Lada Largus (А777АА777) • Загрузка: ', bold: '3/5 задач' },
            { icon: '🛠', text: 'ВОЛС, Настройка Wi-Fi 6, Монтаж КСПВ' },
        ],
        skillTag: { text: '✓ Роутер Wi-Fi 6 в кабель в авто', bg: '#00E676', border: '1px solid #FFCC00' },
        km: '+2.1 км', eta: 'ETA: 09:40', kmColor: '#FFCC00',
        button: { text: 'Назначить', style: 'primary' },
    },
    {
        id: 'ENG-102', name: 'Алексей Смирнов', available: true, recommended: false,
        dot: '#22C55E', nameColor: '#000', border: '1px solid #27272A',
        detailColor: '#A1A1AA',
        details: [
            { icon: '🚶', text: 'Пеший инженер • Загрузка: ', bold: '2/5 задач' },
            { icon: '🛠', text: 'Настройка Wi-Fi, Диагностика линий' },
        ],
        skillTag: { text: '⚠ Нет роутера Wi-Fi 6 в сумке', bg: '#EF4444' },
        km: '+4.8 км', eta: 'ETA: 10:15', kmColor: '#A1A1AA',
        button: { text: 'Выбрать', style: 'secondary' },
    },
    {
        id: 'ENG-111', name: 'Дмитрий Козлов', available: false, recommended: false,
        dot: '#ef4444', nameColor: '#000', border: '1px solid #27272A',
        detailColor: '#A1A1AA',
        details: [
            { icon: '🚗', text: 'Hyundai Solaris • Загрузка: ', bold: '6/5 (Занят)', boldColor: '#EF4444' },
            { icon: '🛠', text: 'Сварка ВОЛС, Монтаж оборудования' },
        ],
        skillTag: null,
        km: '+12.3 км', eta: 'ETA: 10:15', kmColor: '#ef4444',
        button: { text: 'Недоступен', style: 'disabled' },
    },
]