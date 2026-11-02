# Freight Management System: Multi-Company Isolation and Record Rules

| Metadata | Details |
| :--- | :--- |
| **Project** | Freight Management System (`trn_freight`) |
| **Odoo Version** | 19.0 Community / Enterprise |
| **Date** | 2026-11-02 |
| **Author** | Nasim Ullah (Assisted by Antigravity) |
| **Milestone** | Point 3 Completed (Multi-Company Record Rules & Stored Related Company Lines) |

---

## 1. Verbatim Task Prompt

> "3. Multi-company: add a record rule on every freight model, so a user sees only records of their allowed companies. Lines take the company of their parent order (a stored related field)."

---

## 2. Overview & Problem Analysis

In a multi-company Odoo deployment, data isolation between companies is critical:
1. **Parent Transactions:** Orders created under Company A must be invisible to users who only have access to Company B, and vice-versa.
2. **Child Lines:** Child items (`cargo.line`, `route.line`, `order.service`, `track`) must inherit the exact company of their parent order so that direct SQL joins, list views, or reports cannot leak data across company boundaries.
3. **Master Data Flexibility:** Master data such as Ports, Containers, and Routes can be either company-specific or shared globally across all companies when `company_id` is empty (`False`).

---

## 3. Technical Implementation

### 3.1 Stored Related `company_id` on Child Lines

All child line models in `trn_freight/models/freight_shipping.py` and `trn_freight/models/freight_service.py` were updated with stored related `company_id` fields pointing to their parent record:

* **`freight.cargo.line`** (Cargo item lines):
  ```python
  company_id = fields.Many2one(
      'res.company',
      string='Company',
      related='shipping_id.company_id',
      store=True,
      readonly=True,
      index=True,
  )
  ```
* **`freight.route.line`** (Route stops):
  ```python
  company_id = fields.Many2one(
      'res.company',
      string='Company',
      related='shipping_id.company_id',
      store=True,
      readonly=True,
      index=True,
  )
  ```
* **`freight.order.service`** (Service billing lines):
  ```python
  company_id = fields.Many2one(
      'res.company',
      string='Company',
      related='shipping_id.company_id',
      store=True,
      readonly=True,
      index=True,
  )
  ```
* **`freight.track`** (Shipment tracking events):
  ```python
  company_id = fields.Many2one(
      'res.company',
      string='Company',
      related='shipping_id.company_id',
      store=True,
      readonly=True,
      index=True,
  )
  ```
* **`freight.service.line`** (Service template vendor lines in `freight_service.py`):
  ```python
  company_id = fields.Many2one(
      'res.company',
      string='Company',
      related='service_id.company_id',
      store=True,
      readonly=True,
      index=True,
  )
  ```

### 3.2 Indentation Fix in `freight.shipping.create()`

While testing model instantiation with non-default names, a latent bug was discovered in `freight.shipping.create()`:
* **Issue:** `return super().create(vals_list)` was indented inside `if vals.get('name', 'New') == 'New':`. If an order was created with an explicit name, the method returned `None`.
* **Fix:** Following the discipline rule of commenting out rather than deleting:
  ```python
  @api.model_create_multi
  def create(self, vals_list):
      # for vals in vals_list:
      #     if vals.get('name', 'New') == 'New':
      #         vals['name'] = self.env['ir.sequence'].next_by_code('freight.shipping') or 'New'
      #         return super().create(vals_list)
      for vals in vals_list:
          if vals.get('name', 'New') == 'New':
              vals['name'] = self.env['ir.sequence'].next_by_code('freight.shipping') or 'New'
      return super().create(vals_list)
  ```

---

## 4. Multi-Company Record Rules Architecture

Global multi-company rules were defined in `trn_freight/security/freight_security.xml` for all 11 models:

```xml
['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
```

### Complete List of Configured Record Rules:

1. **`freight_shipping_comp_rule`** on `freight.shipping`
2. **`freight_cargo_line_comp_rule`** on `freight.cargo.line`
3. **`freight_route_line_comp_rule`** on `freight.route.line`
4. **`freight_order_service_comp_rule`** on `freight.order.service`
5. **`freight_track_comp_rule`** on `freight.track`
6. **`freight_port_comp_rule`** on `freight.port`
7. **`freight_container_comp_rule`** on `freight.container`
8. **`freight_price_comp_rule`** on `freight.price`
9. **`freight_routes_comp_rule`** on `freight.routes`
10. **`freight_service_comp_rule`** on `freight.service`
11. **`freight_service_line_comp_rule`** on `freight.service.line`

Each rule is configured with `<field name="global" eval="True"/>` without groups, ensuring it applies unconditionally across all users and internal operations.

---

## 5. Empirical Verification and Test Results

Using Odoo's Python environment, empirical testing verified the isolation:

```text
1. Stored related company check: True
   - Order A company: My Company (ID 1)
   - Cargo Line company: My Company (ID 1)
2. User B see Order A (Company A): False (0 orders visible, strictly blocked)
3. Order B created in Company B: True (Company correctly assigned to Company B)
4. User A see Order B (Company B): False (0 orders visible, strictly blocked)
```

Both cross-company read operations were completely blocked by Odoo's SQL domain rewrite at ORM level.

---

## 6. Files Changed

| File Path | Description of Modification |
| :--- | :--- |
| `trn_freight/__manifest__.py` | Version bumped from `19.0.1.0.2` to `19.0.1.0.3` |
| `trn_freight/models/freight_shipping.py` | Added stored related `company_id` on 4 line models; fixed `create()` return |
| `trn_freight/models/freight_service.py` | Added stored related `company_id` on `freight.service.line` |
| `trn_freight/security/freight_security.xml` | Added 11 global multi-company record rules |

---

## 7. Next Step: Point 4 (Automated Test Suites)

With Point 1, Point 2, and Point 3 complete, we proceed to **Point 4**:
* Write tests in `tests/test_freight_order.py` and `tests/test_security.py`:
  1. Totals are calculated correctly.
  2. State transition workflow: Submit -> Confirm -> Done updates order and container states.
  3. Wrong port validation refused for transport type.
  4. Deleting a confirmed order is refused.
  5. Multi-company test: User of Company B cannot read an order of Company A.
