---
title: Checkout v2 — design notes
status: draft
---

# Checkout v2 — design notes

Checkout is split into three steps today. Payment is authorised in the second step and
captured in the third, which is why an abandoned cart can leave a dangling authorisation.
This document describes the design that removes that gap.

## Goals

- One confirmation step instead of three
- No authorisation without a matching capture attempt
- The cart survives a browser reload

## Non-goals

Subscriptions, refunds, and the admin-side order editor stay as they are.

## The flow

| Step | Today | After |
|:-----|:------|:------|
| Address | separate page | inline |
| Payment | authorise | authorise + capture |
| Review | capture | *removed* |

1. The customer submits the single confirmation form.
2. `CheckoutSession` is created and locked for 15 minutes.
3. The payment provider is called once, with `capture: true`.
4. On success the order is written; on failure the session is released.

> The 15-minute lock is what makes step 3 safe to retry. Without it, two tabs could
> submit the same cart twice.

### Failure handling

- [x] Provider timeout — retried once, then surfaced to the customer
- [x] Card declined — the session stays open so another card can be used
- [ ] Provider outage — still just an error page

```python
def confirm(session_id: str) -> Order:
    with lock(session_id, ttl=900):
        payment = provider.charge(session.amount, capture=True)
        return Order.create(session, payment)
```

## Open questions

- Should the lock TTL be configurable per store, or is 15 minutes enough everywhere?
- What happens to a session whose lock expires **while** the provider call is in flight?

See [the API notes](sample-doc.md#the-flow) for the request shape.
