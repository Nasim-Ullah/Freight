
## 1. Module Overview & Business Domain

The **Freight Forwarding & Shipping Suite (`trn_freight`)** is an enterprise-grade logistics and global trade application built natively for **Odoo 19.0**. It manages end-to-end multi-modal freight operations across Ocean, Air, and Land routes, integrating cargo tracking, container lifecycle management, customs declarations, automated customer invoicing, and strict protection locks.

```
+-------------+     +-------------------+     +------------------+     +-------------------+
| Draft Order | --> | Port Validation   | --> | Container Lock   | --> | Transit Tracking  |
| (Cargo/Cost)|     | (Sea / Air / Land)|     | (Avail->Reserved)|     | (Milestone Logs)  |
+-------------+     +-------------------+     +------------------+     +-------------------+
       |                                                                         |
       v                                                                         v
+------------------+                                                    +-------------------+
| Customs Approval | <------------------------------------------------- | Auto Invoicing    |
| (Doc Revisions)  |                                                    | (Customer Invoice)|
+------------------+                                                    +-------------------+
```

---

## 2. Core Architecture & Model Specifications

The module defines **11 interconnected data models** categorized into operational headers, cargo lines, container fleet, multi-modal geography, and customs compliance:

| Model Technical Name | Class / Description | Primary Purpose |
| :--- | :--- | :--- |
| `freight.shipping` | Shipping Order Header | Main business document managing customer, route, transport mode, financial totals, and lifecycle state. |
| `freight.cargo.line` | Cargo Item Lines | Itemized cargo packages, gross/net weight, volume ($m^3$), temperature requirements, and container association. |
| `freight.container` | Container Inventory | Physical container fleet management (20ft, 40ft, Reefer) with automated availability tracking (`available` / `reserved`). |
| `freight.order.service` | Order Charge Lines | Services billed to customer or incurred from vendors (Ocean Freight, Documentation, Fuel Surcharge). |
| `freight.service` | Service Catalog | Master catalog of freight services and standard pricing templates. |
| `freight.port` | Ports & Terminals | Sea ports, airports, and dry ports equipped with multi-modal transport capability flags (`is_air`, `is_water`, `is_land`). |
| `freight.route` | Transit Routes | Master predefined transit corridors linking source and destination ports. |
| `freight.route.line` | Route Transit Legs | Sequential multimodal legs forming a complex intermodal route. |
| `freight.vessel` | Transport Vehicles | Ships, aircraft, and haulage trucks assigned to freight orders. |
| `freight.track` | Transit Milestones | Live tracking updates recording checkpoints, timestamps, locations, and transit status. |
| `custom.clearance` | Customs Compliance | Customs declarations, HS tariff codes, duty amounts, and clearance approval workflow. |
| `clearance.revision` | Customs Revision Log | Immutable audit trail tracking revisions to customs paperwork. |

---

## 3. Deep Dive into Primary Models & Business Logic

### A. Main Freight Order (`freight.shipping`)
- **Key Fields:**
  - `name`: Auto-generated unique sequence (e.g., `FRT/2026/0001`).
  - `partner_id`: Many2one linking to Customer (`res.partner`).
  - `transport_type`: Selection (`land`, `air`, `water`).
  - `loading_port_id` & `discharge_port_id`: Many2one linking to `freight.port`.
  - `state`: Selection (`draft`, `submitted`, `confirmed`, `invoiced`, `done`, `cancel`).
  - `total`: Computed float summing all service sale prices.
  - `services_total`: Computed float summing all vendor service costs.
  - `net_margin`: Computed float (`total - services_total`).
  - `margin_percentage`: Computed percentage margin (`(net_margin / total) * 100`).
  - `invoice_id`: Many2one linking to generated Customer Invoice (`account.move`).
  - `company_id`: Multi-company segregation field with `default=lambda self: self.env.company`.

- **Transport Mode Compatibility Constraint:**
  Prevents selecting incompatible ports for the chosen transport mode:
  ```python
  @api.constrains('loading_port_id', 'discharge_port_id', 'transport_type')
  def _check_port_transport_compatibility(self):
      for record in self:
          mode = record.transport_type
          for port, label in [(record.loading_port_id, "Loading Port"), (record.discharge_port_id, "Discharge Port")]:
              if port:
                  if mode == 'water' and not port.is_water:
                      raise ValidationError(_(f"{label} '{port.name}' does not support Ocean/Water freight!"))
                  elif mode == 'air' and not port.is_air:
                      raise ValidationError(_(f"{label} '{port.name}' does not support Air freight!"))
                  elif mode == 'land' and not port.is_land:
                      raise ValidationError(_(f"{label} '{port.name}' does not support Land transport!"))
  ```

---

### B. Container Fleet & State Transitions (`freight.container` & `freight.cargo.line`)
- Physical containers are monitored for utilization.
- When an order transitions to `confirmed` (`action_confirm()`), assigned containers transition from `available` to `reserved`:
  ```python
  def action_confirm(self):
      for order in self:
          containers = order.cargo_line_ids.mapped('container_id')
          unavailable = containers.filtered(lambda c: c.state != 'available')
          if unavailable:
              raise UserError(_(f"Container(s) {unavailable.mapped('name')} are already reserved!"))
          containers.write({'state': 'reserved'})
      return self.write({'state': 'confirmed'})
  ```
- When an order is completed (`action_done()`) or cancelled (`action_cancel()`), containers are safely returned to `available`.

---

### C. Automated Customer Invoicing Pipeline (`account.move`)
- Executing `action_invoice()` automatically generates a customer invoice directly in Odoo Accounting without manual re-entry:
  ```python
  def action_invoice(self):
      self.ensure_one()
      if self.invoice_id:
          raise UserError(_("An invoice already exists for this shipment!"))
      
      invoice_lines = []
      for service in self.service_line_ids:
          invoice_lines.append(Command.create({
              'product_id': service.service_id.id,
              'name': service.name or service.service_id.name,
              'price_unit': service.sale_price,
              'quantity': 1.0,
          }))
      
      invoice = self.env['account.move'].create({
          'move_type': 'out_invoice',
          'partner_id': self.partner_id.id,
          'company_id': self.company_id.id,
          'invoice_origin': self.name,
          'invoice_line_ids': invoice_lines,
      })
      self.write({'invoice_id': invoice.id, 'state': 'invoiced'})
      return self.action_view_invoice()
  ```

---

### D. Data Integrity & Unlink Protection Lock
- Critical operational orders cannot be accidentally deleted once confirmed or delivered:
  ```python
  def unlink(self):
      for order in self:
          if order.state in ('confirmed', 'invoiced', 'done'):
              raise UserError(_("You cannot delete a confirmed, invoiced, or completed freight order! Please cancel it first."))
      return super().unlink()
  ```

---

## 4. Role-Based Access Control (RBAC) & Multi-Company Security

### Security Groups (`ir.model.access.csv`)
1. **Freight User (`group_freight_user`):** Can view freight orders, create draft shipments, log tracking updates, and upload customs documents.
2. **Freight Manager (`group_freight_manager`):** Full operational authority: order confirmation, cancellation, container release, invoice trigger, and system configuration.

### Multi-Company Record Rules
Ensures absolute data isolation in multi-entity logistics organizations:
```xml
<record id="freight_shipping_multi_company_rule" model="ir.rule">
    <field name="name">Freight Shipping Multi-Company Isolation</field>
    <field name="model_id" ref="model_freight_shipping"/>
    <field name="domain_force">['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]</field>
</record>
```

---

## 5. Automated Test Suite & Quality Assurance

The test suite in `trn_freight/tests/` provides complete automated regression coverage across 4 test suites:

| Test Module | Coverage Scope | Result |
| :--- | :--- | :--- |
| `test_freight_order.py` | State machine transitions, container auto-reservation, port transport constraints, unlink lock. | **Passed (100%)** |
| `test_security.py` | Multi-company isolation between Company A and Company B, RBAC permissions. | **Passed (100%)** |
| `test_tracking_invoicing_locks.py` | Customer invoice generation via `Command.create`, idempotent invoice creation, tracking checkpoints. | **Passed (100%)** |
| `test_custom_clearance.py` | Customs declarations, revision logs, duty amount validation. | **Passed (100%)** |

---

## 6. Roman Urdu Key Takeaways (Interview & Review Prep)

### Senior Developers / Management ko kaise explain karein:

1. **State Machine & Container Sync:**
   - *"Freight order jab `draft` se `confirmed` hota hai, to hum Python code me `cargo_line_ids.mapped('container_id')` se tamam containers ko dhoond kar unka state `reserved` kar dete hain. Jab order `done` ya `cancel` hota hai to containers wapis `available` ho jate hain."*

2. **Port Compatibility Check:**
   - *"Har Port ke paas 3 boolean flags hain: `is_air`, `is_water`, `is_land`. Agar user transport mode 'Air' select kare aur ocean port daal de, to `@api.constrains` foran `ValidationError` raise kar ke save hona block kar deta hai."*

3. **Customer Invoicing Pipeline:**
   - *"Hum ne Odoo 19 ka modern `Command.create(...)` syntax use kiya hai. Ek click par `account.move` me customer invoice generate ho jata hai aur order ka state `invoiced` ho jata hai."*

4. **Multi-Company Security:**
   - *"Record Rules me hum ne `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]` rule lagaya hai, taake Company A ke dispatchers ko Company B ke orders kabhi nazar na aayein."*
