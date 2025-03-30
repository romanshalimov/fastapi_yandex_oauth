# Audio File Service

1. Отредактируйте `.env` файл:
   - Замените `your-client-id` на ваш Яндекс Client ID
   - Замените `your-client-secret` на ваш Яндекс Client Secret
   - Измените `your-secret-key-here` на случайную строку для JWT

2. Запустите сервис с помощью Docker Compose:
```bash
docker-compose up -d
```

3. Проверьте, что сервис запущен:
```bash
docker-compose ps
```

## Использование

1. Откройте в браузере: `http://localhost:8000/docs`

2. Авторизация:
   - Перейдите по адресу: `http://localhost:8000/auth/yandex`
   - Авторизуйтесь через Яндекс
   - Получите токен доступа

3. Использование API:
   - В Swagger UI нажмите "Authorize"
   - Вставьте полученный токен

## Остановка сервиса

docker-compose down

## Очистка данных

Для полной очистки данных (включая базу данных):
docker-compose down -v