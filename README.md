# SimpleBank

SimpleBank is an API-only Django service that provides basic bank account functionality:
- user registration with email and password
- JWT-based authentication
- automatic bank account creation with a unique 10-digit account number
- EUR 10,000 welcome bonus for new users
- balance lookup
- transaction history with optional date filtering
- money transfers with a 2.5% fee or EUR 5 minimum

## Stack

- Python 3.12
- Django
- Django REST Framework
- Gunicorn
- PostgreSQL
- Docker Compose

## Run With Docker

Start the API and PostgreSQL:

```bash
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000/api/
```

The `web` container waits for PostgreSQL, applies migrations, and starts the app with Gunicorn automatically.

## Run Tests

Start only PostgreSQL:

```bash
docker compose up -d db
```

Run the test suite in the app container:

```bash
docker compose run --rm web python manage.py test
```

Tests also use PostgreSQL. The Django test runner creates a separate test database named `test_simple_bank` by default.

## Environment Variables

The application reads database and Django runtime settings from environment variables.

| Variable | Default |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django development key |
| `DJANGO_DEBUG` | `True` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` |
| `POSTGRES_DB` | `simple_bank` |
| `POSTGRES_USER` | `simple_bank` |
| `POSTGRES_PASSWORD` | `simple_bank` |
| `POSTGRES_HOST` | `db` |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_TEST_DB` | `test_simple_bank` |

## API Endpoints

All authenticated endpoints require:

```text
Authorization: Bearer <access-token>
```

### 1. Register

`POST /api/register/`

Request:

```json
{
  "email": "alice@example.com",
  "password": "strong-pass-123"
}
```

Response:

```json
{
  "access": "jwt-access-token",
  "refresh": "jwt-refresh-token",
  "email": "alice@example.com",
  "account_number": "1234567890",
  "balance": "10000.00"
}
```

Behavior:
- creates a new user
- creates a new bank account with a unique 10-digit account number
- credits the EUR 10,000 welcome bonus
- returns a JWT access/refresh token pair

### 2. Login

`POST /api/login/`

Request:

```json
{
  "email": "alice@example.com",
  "password": "strong-pass-123"
}
```

Response:

```json
{
  "access": "jwt-access-token",
  "refresh": "jwt-refresh-token"
}
```

### 3. Get Balance

`GET /api/account/balance/`

Response:

```json
{
  "account_number": "1234567890",
  "balance": "10000.00"
}
```

### 4. List Transactions

`GET /api/transactions/`

Optional query params:
- `from`
- `to`

Both filters accept ISO 8601 date or datetime values.

Example:

```text
GET /api/transactions/?from=2026-04-01&to=2026-04-30
```

Response:

```json
[
  {
    "amount": "10000.00",
    "type": "credit",
    "timestamp": "2026-04-19T16:14:00Z",
    "description": "Welcome bonus"
  }
]
```

### 5. Transfer Money

`POST /api/transfers/`

Request:

```json
{
  "account_number": "0987654321",
  "amount": "100.00"
}
```

Response:

```json
{
  "sender_account_number": "1234567890",
  "receiver_account_number": "0987654321",
  "amount": "100.00",
  "fee": "5.00",
  "total_debited": "105.00",
  "balance": "9895.00"
}
```

Transfer rules:
- sender must be authenticated
- destination account must exist
- transfers to the same account are rejected
- fee is `max(2.5% of amount, EUR 5)`
- sender receives a debit transaction
- receiver receives a credit transaction
- balance updates and transaction creation are atomic

## Notes

- The project uses JWT authentication via `djangorestframework-simplejwt`.
- The service is API-only; no frontend is included.
- The default Docker setup is aimed at local development.
