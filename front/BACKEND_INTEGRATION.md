# Интеграция с бэкендом

Этот файл — единая шпаргалка: что фронт ждёт от бэкенда, в каком формате,
и что уже готово на стороне фронта, чтобы завтра просто подключить реальные ответы
вместо моков. Все перечисленные ниже функции уже написаны в `src/api/*.js` —
их не нужно писать заново, только вызвать в нужном месте компонента (см. комментарии
`🔌 БЭКЕНД` прямо в коде — они указывают на конкретную строку, которую менять).

## Как это устроено на фронте

- `src/api/http.js` — общий axios-инстанс. Базовый адрес берётся из `.env`
  (переменная `VITE_API_URL`, см. `.env.example`). Токен из `localStorage`
  подставляется в заголовок `Authorization: Bearer <token>` автоматически.
  Если бэкенд ответит 401 — фронт сам сотрёт сессию и уведёт на `/auth`.
- Остальные файлы в `src/api/` — по одному на каждую "область" приложения:
  `auth.js`, `dispatcher.js`, `engineer.js`, `candidates.js`, `districts.js`, `profile.js`.
- **Что нужно сделать бэкендеру**: свериться со списком ниже (пути условные,
  их можно поменять — тогда просто меняем URL в соответствующем файле в `src/api/`,
  логика компонентов не трогается).
- **Что нужно сделать фронтендеру завтра**: в каждом месте с пометкой `🔌 БЭКЕНД`
  заменить mock-импорт/console.log на вызов готовой функции.

## Авторизация

| Метод | Путь | Тело запроса | Ответ |
|---|---|---|---|
| POST | `/auth` | `{ login, password }` | `{ token, user: { id, name, role: 'dispatcher' \| 'engineer' } }` |

`role` — обязательное поле, по нему фронт решает, куда вести пользователя после логина.

## Диспетчер (`src/api/dispatcher.js`)

| Метод | Путь | Ответ / тело |
|---|---|---|
| GET | `/dispatcher/stats` | `{ online, mileage, mileageDelta }` (строки, уже отформатированные для показа) |
| GET | `/dispatcher/masters` | `[{ id, name, mode, shift, requests, online }]` |
| GET | `/dispatcher/replanning-events` | `[{ id, requestId, time, title, description, reason, engineerId }]` |
| GET | `/dispatcher/requests?status=unallocated` | `[{ id, date, window, address, service, suggested }]` |
| GET | `/dispatcher/requests?status=distributed` | `[{ id, description, status }]` |
| POST | `/engineers` | тело `{ fio, birthDate, skills, phone, transport }` — создание инженера |
| PATCH | `/engineers/:id` | тело как выше — редактирование |
| POST | `/engineers/:id/remove-from-shift` | снять со смены |
| POST | `/requests/:id/assign` | тело `{ engineerId }` |
| POST | `/requests/:id/return-to-pool` | вернуть заявку в пул |
| POST | `/requests/:id/auto-assign` | авто-распределение |
| POST | `/requests/:id/confirm` | утвердить нераспределённую заявку |
| POST | `/requests/urgent` | тело `{ client, phone, address, fault, when, priority }` |

## Инженер (`src/api/engineer.js`)

| Метод | Путь | Ответ / тело |
|---|---|---|
| GET | `/engineer/requests` | `{ openRequest, queuedRequests }` |
| POST | `/requests/:id/stage` | тело `{ stage: 'take' \| 'start' \| 'stop' }` |
| POST | `/requests/:id/cancel-by-client` | — |

⚠️ Чтобы дёрнуть смену этапа, компоненту `WorkStagesFooter.jsx` нужно будет
добавить проп `requestId` (сейчас его нет вообще, компонент работает "в вакууме").

## Кандидаты на назначение (`src/api/candidates.js`)

| Метод | Путь | Ответ |
|---|---|---|
| GET | `/requests/:id/reassign-candidates` | `[{ id, name, transport, load, deviation, stock, stockOk, isOptimal, reason }]` |
| GET | `/requests/:id/replacement-candidates` | `[{ id, name, available, recommended, transport, load, skills, hasRequiredEquipment, distanceKm, etaMinutes }]` |

**Важно:** цвета, иконки и бейджи (`nameColor`, `dot`, `skillTag.bg` и т.п. в текущих
моках) — это фронтовая логика отображения. Присылать их с бэкенда не нужно, фронт
раскрасит карточку сам на основе `available`/`recommended`/`isOptimal`.

## Районы (`src/api/districts.js` + `ChoiceDistrictModal.jsx`)

| Метод | Путь | Комментарий |
|---|---|---|
| GET | `/districts/export?district=...` | уже реализовано во фронте через `fetch` напрямую (отдаёт файл/blob, не JSON) |
| GET | `/districts` | `[{ id, name }]` — список районов, сейчас захардкожен |
| DELETE | `/districts/:district/data?period=today\|previous` | удаление данных по району |

## Профиль (`src/api/profile.js`)

| Метод | Путь | Ответ |
|---|---|---|
| GET | `/profile` | `{ name, post, status, plan, route, trunk }` |

## Входящие заявки в реальном времени

Сейчас на странице диспетчера (`DispatcherPage.jsx`) новые заявки имитируются
`setInterval` со случайными данными. Когда будет готов реальный канал —
WebSocket или Server-Sent Events (что бэкендеру проще поднять) — на фронте
это меняется в одном месте (`useEffect` в `DispatcherPage.jsx`, уже с пометкой
в коде), формат самого объекта заявки можно оставить как в мок-шаблонах
(`id, priority, address, service, window`).

## Порядок действий на завтра

1. Поднять бэкенд локально/на стенде и вписать его адрес в `.env` (`VITE_API_URL`).
   После правки `.env` — перезапустить `npm run dev`.
2. Начать с авторизации (`AuthPage.jsx`/`AuthForm.jsx`) — без неё нет токена
   и остальные запросы не будут авторизованы.
3. Дальше — по одному блоку из таблиц выше, в компоненте искать пометку
   `🔌 БЭКЕНД` рядом с местом, которое меняем.
4. Если путь/формат ответа у бэкенда отличается от таблицы — правим только
   соответствующий файл в `src/api/`, JSX компонентов не трогаем.
