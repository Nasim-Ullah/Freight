
## 1. Module Overview & Business Domain

The **Staff Transport & Fleet Logistics Suite (`trn_staff_transport`)** is a dedicated workforce mobility application for **Odoo 19.0**. It automates employee corporate transit, recurring shift operations, sequenced route optimization, real-time passenger manifest tracking, driver licensing governance, and on-demand vehicle reservations with collision prevention logic.

```
+--------------------+     +---------------------+     +--------------------+
| Master Routes      | --> | Operating Schedules | --> | Daily Trips Wizard |
| (Sequenced Stops)  |     | (Shift Recurrence)  |     | (Idempotent Gen.)  |
+--------------------+     +---------------------+     +--------------------+
          |                                                       |
          v                                                       v
+--------------------+     +---------------------+     +--------------------+
| Vehicle Booking    |     | Driver & Fleet Sync |     | Passenger Manifest |
| (Collision Check)  |     | (License / Capacity)|     | (Boarded/No-Show)  |
+--------------------+     +---------------------+     +--------------------+
```

---

## 2. Core Architecture & Data Models Breakdown

The module provides **5 standalone core models, 3 model extensions, and 1 batch generation wizard**:

| Technical Name | Model Type | Primary Purpose |
| :--- | :--- | :--- |
| `logistics.transport.route` | Core Model | Transit corridors defining start and end depots, distance, and transit duration. |
| `logistics.transport.stop` | Core Model | Sequenced bus stops with geocoding (Lat/Lon), arrival ETAs, and boarding rules. |
| `logistics.transport.schedule` | Core Model | Recurring operating templates with float departure times and weekday recurrence. |
| `logistics.transport.trip` | Core Model | Executed daily trip records tracking live departure/arrival and vehicle capacity. |
| `logistics.transport.trip.passenger`| Core Model | Passenger manifest tracking individual employee boarding status. |
| `logistics.transport.vehicle.request`| Core Model | On-demand ad-hoc corporate vehicle bookings with collision prevention. |
| `res.partner` (Extension) | Model Extension | Driver profile extension (`is_driver`, license number, expiry, medical clearance). |
| `fleet.vehicle` (Extension) | Model Extension | Vehicle capacity extension (`seating_capacity`, AC availability). |
| `hr.employee` (Extension) | Model Extension | Employee transport profile (`transport_route_id`, `home_stop_id`). |
| `logistics.generate.trips.wizard` | TransientModel | Automated batch trip generation wizard with idempotency protection. |

---

## 3. Deep Dive into Primary Models & Business Logic

### A. Sequenced Route & Geocoded Stops (`logistics.transport.route` & `logistics.transport.stop`)
- Each Route contains multiple sequenced stops (`stop_ids` One2many).
- Stops use a strict numerical `sequence` field to order intermediate stops between depot and headquarters.
- **Fields on Stop:** `name`, `sequence`, `latitude`, `longitude`, `eta_minutes`, `pickup_allowed`, `dropoff_allowed`.

---

### B. Master Schedules & Daily Trips (`logistics.transport.schedule` & `logistics.transport.trip`)
- **Operating Schedule:**
  - `departure_time`: Float field representing 24-hour time (e.g. `8.5` = 8:30 AM, `17.25` = 5:15 PM).
  - `direction`: Selection (`inbound` morning pickup, `outbound` evening drop-off).
  - Recurrence Flags: Booleans `monday` through `sunday`.
  - `vehicle_id` & `driver_id`: Pre-assigned default transport assets.
- **Daily Trip Lifecycle:**
  - States: `draft` $ightarrow$ `in_progress` $ightarrow$ `completed` (or `cancelled`).
  - Monitors `total_passengers` against `vehicle_id.seating_capacity`.
  - Records real timestamps: `actual_departure` and `actual_arrival`.

---

### C. Passenger Manifest Lifecycle (`logistics.transport.trip.passenger`)
- Tracks each employee's boarding lifecycle on the trip:
  - `state`: Selection (`booked`, `boarded`, `no_show`, `cancelled`).
  - `pickup_stop_id` & `dropoff_stop_id`: Exact boarding and disembarkation locations.
  - Dispatchers or drivers can record boarding via quick check-in actions.

---

### D. Dedicated Driver Management (`res.partner` Extension)
- Extends standard Odoo Contacts with transport credentials:
  - `is_driver`: Boolean flag marking the partner as an authorized transport driver.
  - `driver_license_number`: Legal commercial driver's license ID.
  - `license_expiry_date`: Expiry date with proactive renewal validation.
  - `medical_check_date`: Health and medical fitness compliance date.
- **Dynamic Selection Domain Filter:**
  Trip and schedule forms restrict driver Many2one fields so only qualified drivers appear:
  ```xml
  <field name="driver_id" domain="[('is_driver', '=', True)]"/>
  ```

---

## 4. Advanced Mathematical Algorithms & Timezone Engine

### A. Idempotent Batch Trip Generation Wizard (`generate.trips.wizard`)
Corporate transport managers generate daily or weekly trips with one click.
- **Idempotency Guarantee:** Running the wizard multiple times on the same date will NEVER create duplicate trips:
  ```python
  existing_trip = self.env['logistics.transport.trip'].search([
      ('date', '=', target_date),
      ('schedule_id', '=', schedule.id),
      ('route_id', '=', route.id),
      ('direction', '=', schedule.direction),
      ('state', '!=', 'cancelled'),
  ], limit=1)

  if existing_trip:
      continue  # Idempotent skip: trip already scheduled!
  ```

- **Timezone Float-to-UTC Transformation:**
  Odoo strictly stores datetimes in UTC, but schedules are defined in the user's local timezone:
  ```python
  import pytz
  from datetime import datetime, time

  # 1. Split float time into hour and minute components
  hours = int(float_val)
  minutes = int(round((float_val - hours) * 60))

  # 2. Combine with date to create naive local datetime
  local_dt = datetime.combine(target_date, time(hour=hours, minute=minutes))

  # 3. Localize to user's timezone and convert to UTC
  user_tz = pytz.timezone(self.env.user.tz or 'UTC')
  localized_dt = user_tz.localize(local_dt)
  utc_dt = localized_dt.astimezone(pytz.UTC).replace(tzinfo=False)
  ```

---

### B. Mathematical Vehicle Collision Prevention Engine
For ad-hoc corporate vehicle bookings (`logistics.transport.vehicle.request`), vehicles must not be double-booked across overlapping time windows:

$$	ext{Collision Detected} \iff (	ext{Start}_A < 	ext{End}_B) \land (	ext{End}_A > 	ext{Start}_B)$$

```python
@api.constrains('vehicle_id', 'date_from', 'date_to', 'state')
def _check_vehicle_booking_collision(self):
    for req in self:
        if req.state in ('approved', 'assigned') and req.vehicle_id:
            collision = self.search([
                ('id', '!=', req.id),
                ('vehicle_id', '=', req.vehicle_id.id),
                ('state', 'in', ('approved', 'assigned')),
                ('date_from', '<', req.date_to),    # Start_A < End_B
                ('date_to', '>', req.date_from),    # End_A > Start_B
            ], limit=1)
            if collision:
                raise ValidationError(_(
                    f"Vehicle '{req.vehicle_id.name}' is already booked between "
                    f"{collision.date_from} and {collision.date_to}!"
                ))
```

---

## 5. Automated Test Suite & Quality Assurance

The test suite in `trn_staff_transport/tests/test_staff_transport.py` (36KB) validates every business flow:

| Test Scenario | Validation Focus | Result |
| :--- | :--- | :--- |
| `test_route_stops_sequence` | Sequenced stop auto-ordering and ETA accumulation. | **Passed (100%)** |
| `test_driver_domain_filter` | Only partners with `is_driver=True` appear in driver dropdowns. | **Passed (100%)** |
| `test_trip_generation_idempotency` | Multiple wizard runs produce zero duplicate trip records. | **Passed (100%)** |
| `test_timezone_conversion` | Accurate float-time to UTC conversion across global timezones. | **Passed (100%)** |
| `test_vehicle_overlap_collision` | Overlapping vehicle requests trigger `ValidationError`. | **Passed (100%)** |
| `test_passenger_manifest_boarding`| State transitions: `booked` $ightarrow$ `boarded` / `no_show`. | **Passed (100%)** |

---

## 6. Roman Urdu Key Takeaways (Interview & Review Prep)

### Senior Developers / Management ko kaise explain karein:

1. **Driver Filter Domain:**
   - *"Hum ne `res.partner` ko inherit kar ke `is_driver` boolean add kiya. Views me Many2one field par `domain="[('is_driver', '=', True)]"` lagaya hai taake driver select karte waqt aam contacts, companies ya vendors dropdown me nazar na aayein."*

2. **Timezone Math:**
   - *"User float time (e.g. 8.5 = 8:30 AM) apne local time me deta hai. Hum pehle hours aur minutes split karte hain, phir `pytz.timezone(self.env.user.tz)` se localize karte hain aur akhir me UTC me convert kar ke database me save karte hain."*

3. **Collision / Overlap Formula:**
   - *"Agar do time slots takra rahe hain ya nahi, iska standard mathematical formula `Start_A < End_B and End_A > Start_B` hai. Agar search me koi record mil jaye to foran `ValidationError` show kar dete hain."*

4. **Wizard Idempotency:**
   - *"Batch trip generator har schedule ke liye pehle database me search karta hai ke kya is date aur route ka trip pehle se mojood hai? Agar hai to `continue` kar deta hai, is liye bar bar wizard chalane se duplicate data create nahi hota."*
