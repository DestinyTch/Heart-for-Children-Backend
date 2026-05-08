# Hearts for Children — REST API

A secure, production-ready Flask backend that processes charity donations, stores them in MongoDB, uploads proof images to Cloudinary, and sends real-time Telegram alerts.

---

## Project Structure

```
hearts-api/
├── app.py                        # Application factory & entry point
├── config.py                     # All configuration loaded from .env
├── requirements.txt
├── .env.example                  # Copy → .env, fill in secrets
├── .gitignore
├── routes/
│   ├── donations.py              # POST /api/donate, POST /api/verify/<ref_id>
│   └── stats.py                  # GET /api/stats
├── services/
│   ├── cloudinary_service.py     # SDK init + sequential image upload
│   ├── telegram_service.py       # sendMessage + sendMediaGroup
│   └── validators.py             # Pure validation (email, method, images)
└── tests/
    └── test_validators.py        # Pytest unit tests for validation logic
```

---

## Quick Start

### 1. Clone & create a virtual environment

```bash
git clone <your-repo>
cd hearts-api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Open .env and fill in every value
```

| Variable | Where to get it |
|---|---|
| `MONGO_URI` | MongoDB Atlas → Connect → Drivers |
| `CLOUDINARY_CLOUD_NAME/KEY/SECRET` | Cloudinary Dashboard → Settings → Access Keys |
| `TELEGRAM_BOT_TOKEN` | Create a bot via [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Message [@userinfobot](https://t.me/userinfobot) |
| `ADMIN_SECRET` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |

### 3. Run the development server

```bash
python app.py
# Server starts at http://127.0.0.1:5000
```

---

## API Reference

### `GET /api/stats`

Returns fundraising totals. Only counts **verified** donations.

**Response `200`**
```json
{
  "total_raised": 1250.00,
  "donor_count": 48
}
```

---

### `POST /api/donate`

Accepts a multipart/form-data donation submission.

**Form Fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | ✅ | Donor email (validated) |
| `name` | string | — | Donor name (omit or empty = 'Anonymous') |
| `anonymous` | string | — | `"1"` to anonymise; `"0"` default |
| `method` | string | ✅ | `btc`, `sol`, `usdt`, `amazon`, `apple`, `steam`, `sephora`, `razer` |
| `amount` | string | — | Gift card face value in USD |
| `code` | string | — | Gift card redemption code |
| `proof_0` … `proof_4` | file | — | Up to 5 images (JPEG/PNG/WEBP, max 5 MB each) |

**Response `201`**
```json
{
  "success": true,
  "ref_id": "HFC-A3X9KZ7Q2F"
}
```

**Error responses**

| Code | Meaning |
|---|---|
| `400` | Validation failure (bad email, invalid method, oversized image) |
| `500` | Cloudinary upload error or MongoDB write failure |

---

### `POST /api/verify/<ref_id>` *(Admin only)*

Moves a donation from `pending` → `verified`, making it count in the public stats.

**Headers**
```
X-Admin-Secret: <your ADMIN_SECRET value>
```

**Response `200`**
```json
{
  "success": true,
  "ref_id": "HFC-A3X9KZ7Q2F",
  "status": "verified"
}
```

**cURL example**
```bash
curl -X POST http://127.0.0.1:5000/api/verify/HFC-A3X9KZ7Q2F \
     -H "X-Admin-Secret: your_admin_secret_here"
```

---

## MongoDB Document Schema

```js
{
  "_id":        ObjectId,
  "ref_id":     "HFC-A3X9KZ7Q2F",
  "email":      "donor@example.com",
  "name":       "Jane Doe",
  "anonymous":  false,
  "method":     "steam",
  "amount":     "25",
  "code":       "XXXX-XXXX-XXXX",
  "proof_urls": [
    "https://res.cloudinary.com/..."
  ],
  "status":     "pending",          // → "verified" after admin approval
  "created_at": ISODate("..."),
  "verified_at": ISODate("...")     // present only after verification
}
```

**Recommended indexes (run once in Atlas or mongosh)**
```js
db.donations.createIndex({ ref_id: 1 }, { unique: true })
db.donations.createIndex({ status: 1 })
db.donations.createIndex({ created_at: -1 })
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Deployment Checklist

- [ ] Set `FLASK_DEBUG=false` in production `.env`
- [ ] Use a production WSGI server: `gunicorn -w 4 "app:create_app()"`
- [ ] Restrict `ALLOWED_ORIGINS` to your live frontend domain
- [ ] Set a strong `ADMIN_SECRET` (32+ character hex)
- [ ] Enable MongoDB Atlas IP whitelist
- [ ] Store `.env` as platform secrets (Heroku Config Vars, Railway Variables, etc.)
