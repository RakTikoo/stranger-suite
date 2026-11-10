# MockPay API (v2)

Base URL: http://127.0.0.1

## Authentication and versioning

Send your test key as usual, and always send this header:

X-Api-Version: 2

## Create a customer

POST /customers

Example body: {"name": "Ada"}

## Charge a customer

POST /charges

Example body: {"customer_id": "cus_1", "amount_cents": 1000}

The field "amount_cents": is required. Amounts are in cents.

## Refund a charge

POST /refunds

Example body: {"charge_id": "chg_1"}
