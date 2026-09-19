# QuickBook

A Django REST Framework backend for an event booking platform — built as a machine test assignment.

QuickBook lets customers browse and book event tickets, and includes a binary referral network and a custom staff dashboard for managing vendors, events, and bookings.

## Features

- **Authentication** — Custom email-based user model, token authentication, protected endpoints
- **Event Booking** — Browse, search, filter, book, cancel, and view booking history, with concurrency-safe seat reservations
- **Binary Referral Network** — Automatic BFS placement, referral tree, root lookup, and left/right team stats
- **Staff Dashboard** — Custom-built admin console (not Django Admin) for managing vendors, events, and bookings
- **API Docs** — Interactive Swagger UI and OpenAPI 3.0 schema

## Tech Stack

Python 3.11 · Django 5.2 · Django REST Framework · drf-spectacular · SQLite

## Project Structure

```
QuickBook/
├── accounts/     # Custom user model, auth, referral tree logic
├── events/       # Events, vendors, bookings, concurrency-safe booking logic
├── dashboard/    # Custom staff dashboard (views, forms, templates)
├── quickbook/    # Project settings and root URLs
├── manage.py
└── requirements.txt
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # create a staff account
python manage.py runserver
```

| App | URL |
|---|---|
| Landing page | `http://127.0.0.1:8000/` |
| Staff dashboard | `http://127.0.0.1:8000/dashboard/` |
| REST API | `http://127.0.0.1:8000/api/` |
| Swagger docs | `http://127.0.0.1:8000/api/docs/` |

## API Reference

**Auth**
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register/` | Register a new user (optional `referral_code`) |
| POST | `/api/auth/login/` | Log in and receive an auth token |
| POST | `/api/auth/logout/` | Invalidate the current token *(auth required)* |

**Events**
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/events/` | List active events — supports `?search=`, `?location=`, `?vendor=`, `?ordering=`, `?page=` |
| GET | `/api/events/<id>/` | Event detail |

**Bookings** *(auth required)*
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/bookings/` | List the current user's bookings |
| POST | `/api/bookings/` | Book tickets — `{"event": <id>, "quantity": <int>}` |
| GET | `/api/bookings/<id>/` | Booking detail |
| POST | `/api/bookings/<id>/cancel/` | Cancel a booking and restore seats |

**Referrals** *(auth required — account owner or staff only)*
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/referrals/<user_id>/tree/` | Full downline tree |
| GET | `/api/referrals/<user_id>/root/` | Top-level ancestor |
| GET | `/api/referrals/<user_id>/stats/` | Left/right/total team counts |

Full interactive reference: `/api/docs/`

## Design Notes

- **Booking concurrency**: seat reservation uses a conditional atomic `UPDATE` with `F()` expressions (`available_seats__gte=quantity`), so two simultaneous booking requests can't oversell the same seat. Cancellations restore seats the same way.
- **Referral placement**: new users are placed via deterministic breadth-first search, filling the leftmost open slot first.
- **Access control**: the staff dashboard and referral endpoints are restricted to staff/account owners; Django's built-in admin site is not exposed.

## Testing

```bash
python manage.py test
```

82 tests covering authentication, booking validation and concurrency, referral placement and access control, dashboard permissions, and the API schema — all passing.

## Author

Anjali CH — [github.com/anjalich04](https://github.com/anjalich04)