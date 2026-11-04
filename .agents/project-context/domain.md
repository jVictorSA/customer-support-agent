# Domain Context

This is the versioned summary of the product scope, store rules and planned data
model. It is the repository's reference for business behavior. It describes
intended behavior, not implemented code.

## Store profile

- **Empório da Música** — musical instrument retailer in Campo Grande/MS,
  founded in 2008, serving beginners, intermediate and professional musicians.
- Sells **musical instruments only** (guitars, basses, acoustic guitars, drums,
  keyboards, wind instruments, orchestral strings, ukuleles). It does **not**
  sell accessories such as strings, picks, cables, cases, pedals or amplifiers.
- Customer service runs through WhatsApp/phone and in person. Hours: Monday to
  Friday 09:00–18:00, Saturday 09:00–13:00, closed Sundays and holidays.
- Tone of voice: informal but professional, welcoming, like a friend who knows
  music. Avoid robotic or excessively formal language.

## Agent scope

The product is a text customer-support agent that:

- assumes the store persona and greets/answers in the store's tone;
- answers general store questions (address, hours, payment, policies);
- consults operational data for price, availability, order status and tracking;
- applies store policies for exchanges, returns, shipping, promotions and
  warranty;
- handles out-of-scope requests (accessories the store does not sell) politely
  and redirects the customer;
- never invents price, stock, order status, delivery deadline or promotion
  validity — these must come from system data;
- hands off to a human when a complaint or decision exceeds its authority.

## Planned data model

The operational model has six tables. No ORM models or migrations exist yet.

- **categories** — `category_id` (int), `name`, `description`. One category has
  many products.
- **products** — `product_id` (int), `price_brl` (float), `name`,
  `category_id` (FK), `description`, `stock_quantity` (int), `status`
  (`active` | `coming_soon` | `discontinued`), `specs` (JSON), `created_at`.
- **customers** — `customer_id` (int), `name`, `phone`, `email`, `city`. One
  customer has many orders.
- **orders** — `order_id` (int), `customer_id` (FK), `order_date`,
  `status` (`cancelled` | `confirmed` | `delivered` | `pending` | `shipped`),
  `total_brl` (float), `payment_method`
  (`boleto` | `pix` | `debit` | `credit_3x` | `credit_6x` | `credit_12x`),
  `tracking_code`, `estimated_delivery`, `notes`.
- **order_items** — `order_id` (FK), `product_id` (FK), `quantity` (int).
  Join table between orders and products.
- **promotions** — `promotion_id` (int), `product_id` (FK),
  `discount_percent` (int), `description`, `is_active` (bool). One product may
  have promotions.

## Business rules to preserve

### Payment

- PIX: 5% discount on the list price.
- Debit card: full payment, all brands.
- Credit card: up to 12 interest-free installments, minimum installment
  R$ 100.00.
- Boleto: full payment, clears in up to 3 business days.
- Installments: up to 3x with no minimum (except purchases below R$ 50.00);
  4x–6x with minimum installment R$ 80.00; 7x–12x with minimum R$ 100.00.
- Combined payment methods are allowed only for purchases above R$ 2,000.00.

### Exchanges, returns and warranty

- Online purchase withdrawal: request within 7 calendar days of receipt, no
  justification required; product in original packaging, unused, with all
  accessories and manuals; refund in the original payment method within 10
  business days; return shipping paid by the store.
- Defective product: exchange within 30 calendar days of purchase; after that,
  the customer goes to the manufacturer warranty, with the store able to
  intermediate on request. Damage from misuse, drops, excess humidity or
  unauthorized modifications is not covered.
- Exchange by preference (color, model, size): within 7 days, subject to
  availability, product in perfect condition and original packaging; price
  differences are charged or refunded.
- Not eligible: customized/setup instruments, final-sale clearance items, wind
  instrument mouthpieces (hygiene).
- Legal warranty: 90 days against manufacturing defects from receipt.
  Manufacturer warranty varies from 6 months to 2 years.
- Warranty exclusions: natural wear (frets, strings, felt, mouthpiece reeds),
  misuse/drops/extreme weather, third-party repairs, cosmetic damage that does
  not affect functionality.

### Shipping and delivery

- Campo Grande metropolitan area: free shipping for orders above R$ 500.00;
  flat R$ 35.00 below that; delivery in 1–3 business days by the store's
  motoboy; customer contacted by phone before delivery.
- Other cities: Correios PAC (5–12 business days), Correios SEDEX (2–5), or
  Jadlog .package (3–8); shipping calculated from destination CEP, weight and
  dimensions; large instruments may require an individual quote.
- Tracking code format: `BR` + 9 alphanumeric characters + `BR`; sent by e-mail
  and WhatsApp when the order ships.
- All shipments include insurance; on damage, the customer should refuse
  delivery and contact the store immediately.

### Promotions

- Campaigns: store anniversary (August, 10–25%), Black Friday (November,
  15–30%), back-to-school (February), stock clearance, Musician's Week
  (around November 22).
- Promotions are not cumulative. The 5% PIX discount does not apply to
  promotional prices.
- Promotions are subject to stock; sold-out items do not grant a rain check.
- Promotional prices must be shown with the original price and discount
  percentage.
- Always verify whether a promotion is currently active before confirming it.

### Privacy (LGPD)

Personal data (name, phone, e-mail, address) is used only for order processing
and delivery, order/tracking communication, marketing with explicit consent,
and legal/fiscal obligations. Do not share customer data with third parties for
marketing. Customers may request deletion through the store's service channels.

## Implementation status

- Business entities, repositories, use cases, AI/provider integration and
  authentication do not exist yet.
- The only implemented module is `health`, used as the architecture reference.
- The next modules should follow `.agents/project-context/architecture.md` and
  the `new-module` skill.
