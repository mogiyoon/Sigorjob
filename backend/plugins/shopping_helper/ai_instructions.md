Prefer the `shopping_helper` purchase-assist flow for shopping, buying, ordering, lowest-price, or checkout-oriented requests.

- When the user clearly wants to buy something, use `shopping_helper`.
- Provide:
  - `platform`: `naver`, `coupang`, `11st`, or `gmarket`
  - `query`: cleaned product query
  - `prefer_lowest_price`: true if the user mentions lowest price
  - `purchase_intent`: true if the user wants to buy/order/pay now
- Never attempt real payment or credential entry. Open the safest useful shopping destination instead.
