# 📘 Odoo 19 Technical Review & Interview Guide (Roman Urdu)
### Core Architecture, ORM, Security & Transport Logistics Concepts

---

## 1. Core Framework & Basic ORM

### Q1: `name` aur `_rec_name` me kya farq hai?
- **`name`** database ka ek normal field (column) hai jo kisi record ka title ya label save karta hai.
- **`_rec_name`** Odoo model ka ek special attribute (setting) hai. Yeh Odoo ko batata hai ke Many2one dropdowns, search bar aur breadcrumbs me record ka display name dikhane ke liye *konsa field* use karna hai.
- Odoo by default `name` field dhoondta hai. Lekin agar model me `name` ke bajaye koi doosra field ho (jaise vehicle ka `license_plate` ya code), to hum `_rec_name = 'license_plate'` set kar dete hain.

---

### Q2: `active = False` karne se kya hota hai, aur archived records kaise dekhte hain?
- `active = False` karne se record table se delete nahi hota, balki **archive (soft-delete)** ho jata hai.
- Odoo ka ORM automatically tamam normal searches aur dropdowns me hidden filter `[('active', '=', True)]` laga deta hai, jis se archived records aam users ko nazar nahi aate.
- **Archived records dekhne ka tareeqa:**
  1. **UI me:** Search bar me **Filters → Archived** select karein.
  2. **Python code me:** `self.with_context(active_test=False).search(...)` use karein.

---

### Q3: Odoo ko har model ke liye access row (`ir.model.access.csv`) kyun chahiye hoti hai?
- **Security by Default:** Modern Odoo me agar kisi custom model ki entry `ir.model.access.csv` me na ho, to Superuser (`sudo`) ke ilawa koi bhi user us model ke records ko Read, Write, Create ya Delete nahi kar sakta aur Odoo `AccessError` throw karta hai.
- Har row 4 basic permissions define karti hai: `perm_read`, `perm_write`, `perm_create`, aur `perm_unlink` (1 = Ijazat hai, 0 = Blocked).

---

### Q4: `-u` kab zaroori hota hai aur server restart kab kafi hota hai?
- **Sirf Restart kafi hai:** Jab aap ne sirf existing Python functions ke andar ka code/logic change kiya ho (jaise calculation formula, validation message). Python code restart par direct RAM me reload ho jata hai.
- **`-u` (Module Upgrade) zaroori hai:** Jab bhi aap:
  1. Koi XML file change karein (views, menus, actions, reports, sequences).
  2. Model structure change karein (naya field add karein, field type badlein, ya attributes jaise `store=True`, `tracking=True` lagayein).
  3. Security files update karein (`ir.model.access.csv` ya record rules).
  `-u` in tamam changes ko PostgreSQL database me sync aur save karta hai.

---

## 2. Fields, Methods & UI Logic

### Q5: Computed field ko `store=True` kab chahiye hota hai?
By default computed fields database me save nahi hotay, screen khulne par on-the-fly calculate hotay hain. `store=True` tab lagana zaroori hai jab:
- Us field par **Search, Filter ya Group by** karna ho.
- List view me us field par **Sorting / Ordering** karni ho.
- Us field ko **Record Rules** (security) me use karna ho.
- Calculation heavy ho aur bar bar recalculate hone se system slow hota ho.

> **Rule:** `store=True` ke sath hamesha `@api.depends('...')` lagana lazmi hota hai taake Odoo ko pata chale kab recalculate karna hai.

---

### Q6: `@api.onchange` data protect karne ke liye kafi kyun nahi hai?
- `@api.onchange` sirf **frontend browser** me chalta hai jab user screen par form fill karta hai.
- Yeh tab **bilkul nahi chalta** jab:
  1. Backend Python code se records create/update hon (`create()` ya `write()`).
  2. Excel / CSV file se data import kiya jaye.
  3. External API (mobile app, website, integrations) se data aaye.
- Asli data security aur integrity ke liye hamesha **`@api.constrains`** ya ORM overrides use karte hain jo database level par har soorat me chalte hain.

---

### Q7: Odoo 19 me `create` method ko list of values (`vals_list`) kyun milti hai?
- Odoo ke modern multi-create architecture (`@api.model_create_multi`) ki wajah se `create(self, vals_list)` ko dictionaries ki list milti hai (`[{...}, {...}]`).
- **Wajah (Batch Performance):** Loop me 100 dafa alag alag SQL queries chalane ke bajaye, 100 records ko ek hi SQL query (`INSERT INTO ... VALUES (...), (...)`) se insert karna 10 se 50 guna zyada tez hota hai.

---

### Q8: Button hide karne (`invisible`) aur Python me state check karne me kya farq hai?
- **Button hide karna (XML `invisible`):** Yeh sirf user ke dekhne (UI) ki sahulat hai taake ghalat button par click na ho. Lekin chalak user browser dev tools, RPC ya script ke zarye us button ke function ko call kar sakta hai.
- **Python me state check karna (`if self.state != 'draft': raise UserError(...)`):** Yeh **real backend security** hai. Chahe button visible ho ya na ho, agar record ghalat state me hoga to Python foran error throw kar ke action block kar dega.
- **Best Practice:** Dono use karein—button hide karein achi UI ke liye, aur Python me check karein security ke liye.

---

## 3. Security, Testing & System Environment

### Q9: Access Rights aur Record Rules me kya farq hai?
- **Access Rights (`ir.model.access.csv`):** Yeh **Table / Model level** par permission deta hai (Jaise: Kya is user ko Sales Order ka table parhne, likhne, ya delete karne ki ijazat hai ya nahi?).
- **Record Rules (`ir.rule`):** Yeh **Row / Record level** par filter lagata hai (Jaise: Sales Order table to khul gaya, lekin user ko *sirf apni company ya apne banaye huay orders* nazar aayenge, doosro ke nahi).

---

### Q10: Test local working database par pass aur nayi database par fail kyun ho sakta hai?
- Local database me purana demo data, manually banaye huay records, ya doosray modules pehle se install hotay hain.
- Nayi database bilkul saaf hoti hai. Agar test kisi hardcoded ID (jaise `partner_id = 1`) par depend karta ho, ya `__manifest__.py` me kisi zaroori module ki dependency miss ho, ya test ne apna data khud `setUpClass` me create na kiya ho, to test fresh database par fail ho jata hai.

---

### Q11: `sudo()` kya skip karta hai aur normal code me dangerous kyun hai?
- `sudo()` code ko Superuser (`SUPERUSER_ID`) ki power de deta hai, jis se tamam Access Rights aur Record Rules bypass ho jaate hain.
- **Khatra:** Agar isay aam user actions me laparwahi se use kiya jaye to aam user doosri company ya secret departments ka confidential data dekh sakta hai ya delete kar sakta hai.
- **Kab use karein:** Sirf background automated tasks (jaise sequence generator, background mail queue, ya audit logging) me use karein.

---

## 4. Wizards & Action Windows

### Q12: Wizard `TransientModel` kyun hota hai aur uske records ka kya banta hai?
- Wizard temporary popups aur user input lene ke liye hota hai.
- `TransientModel` ke records ko Odoo ka automated vacuum cron job har roz database se permanently delete kar deta hai taake hazaron temporary popup records se database bhari na ho.

---

### Q13: Button method doosra form open karne ke liye kya return karta hai?
Ek **Action Dictionary** (`ir.actions.act_window`) return karta hai:
```python
return {
    'name': 'Trip Details',
    'type': 'ir.actions.act_window',
    'res_model': 'logistics.transport.trip',
    'res_id': trip.id,
    'view_mode': 'form',
    'target': 'current',  # ya popup ke liye 'new'
}
```

---

## 5. Data Integrity & Protection Locks

### Q14: Lock sirf view me `readonly` ke bajaye Python me kyun hona chahiye?
- XML ka `readonly="1"` sirf user ko browser screen par typing karne se rokta hai.
- Lekin API calls, Excel imports, ya script ke zarye locked fields ko asani se update kiya ja sakta hai.
- Python ke `write()` aur `unlink()` methods me check lagane se backend level par data 100% lock ho jata hai aur koi bhi confirmed/invoiced shipment ko modify ya delete nahi kar sakta.

---

### Q15: `Command.create` kya hai aur invoice lines ke liye kyun use hota hai?
- Odoo ka modern API hai jo puranay `(0, 0, vals)` tuple syntax ki jagah use hota hai.
- `Command.create({...})` safely memory me new child record (jaise `account.move.line`) instantiate kar ke parent invoice (`account.move`) ke sath attach kar deta hai. Yeh clean, readable aur type-safe hota hai.

---

### Q16: Emails button ke andar foran send hone ke bajaye queue kyun hoti hain?
- Direct email bhejne me external SMTP mail server se live connect hona parta hai. Agar mail server slow ho ya internet slow ho, to user ka browser hang ho jayega aur button ghoomta rahega.
- Emails ko queue karne se button ek fraction of second me complete ho jata hai aur background cron job aasaani se emails deliver kar deta hai.

---

## 6. Reporting & QWeb Views

### Q17: `t-field` aur `t-esc` / `t-out` me kya farq hai?
- **`t-field`:** Odoo ka smart directive hai jo field ki formatting (currency symbol `$ / Rs`, user timezone, date format) ko system settings ke mutabiq automatically format karta hai.
- **`t-esc` / `t-out`:** Raw text print karta hai baghair kisi automatic currency ya timezone formatting ke.

---

### Q18: Header company logo aur address kahan se aate hain?
Standard QWeb template `<t t-call="web.external_layout">` se aate hain. Yeh automatically print hone walay document ki linked `company_id` (`res.company`) ka logo, address, phone aur VAT number utha kar header me draw kar deta hai.

---

### Q19: `_inherit` baghair `_name` ke aur naye `_name` ke sath me kya farq hai?
- **Baghair `_name` ke (Extension):** Mojooda model aur table ke andar naye fields aur methods add karta hai (jaise `res.partner` me `is_driver` add kiya). Naya database table nahi banta.
- **Naye `_name` ke sath (Prototype):** Ek bilkul naya model aur naya table banata hai jo puranay model ki tamam khusosiyat ko copy karta hai.

---

### Q20: Standard view copy karne ke bajaye `xpath` kyun use karte hain?
**Future Upgradability ke liye!** Agar poori view copy karein to Odoo ke anay walay updates aur bug fixes miss ho jayenge. `xpath` se hum sirf wahi specific tag ya field change karte hain jahan zaroorat ho, baqi poori view original rehti hai.

---

### Q21: `tracking=True` kya karta hai?
Jab field par `tracking=True` laga ho aur model me `mail.thread` ho, to jab bhi koi user us field ko change karega to Chatter me audit log ban jayega (*Kis ne change kiya, kab kiya, pehle kya tha aur ab kya hai*).

---

## 7. Staff Transport, Timezones & Mathematical Logic

### Q22: Odoo Datetime UTC me store karta hai. Local date aur float time ko UTC Datetime me kaise convert karte hain?
1. Float time se hours aur minutes nikaalein (jaise `8.5` → `8` hours, `30` mins).
2. Date aur time ko mila kar local naive datetime banayein.
3. User ke timezone (`self.env.user.tz`) se localize karein.
4. `.astimezone(pytz.UTC)` se UTC me convert kar ke timezone info hata kar database me save karein.

```python
import pytz
from datetime import datetime, time

hours = int(float_val)
minutes = int(round((float_val - hours) * 60))
local_dt = datetime.combine(target_date, time(hour=hours, minute=minutes))
user_tz = pytz.timezone(self.env.user.tz or 'UTC')
localized_dt = user_tz.localize(local_dt)
utc_dt = localized_dt.astimezone(pytz.UTC).replace(tzinfo=False)
```

---

### Q23: Trip generation ko bina duplicate ke safe (Idempotent) kaise banaya?
Wizard trip banane se pehle check karta hai ke kya is `date`, `route_id`, `schedule_id` aur `direction` ka active trip pehle se mojood hai?

```python
existing_trip = self.env['logistics.transport.trip'].search([
    ('date', '=', target_date),
    ('schedule_id', '=', schedule.id),
    ('route_id', '=', route.id),
    ('direction', '=', schedule.direction),
    ('state', '!=', 'cancelled'),
], limit=1)

if existing_trip:
    continue  # Skip duplicate!
```
Agar mojood ho to usay skip kar deta hai. Is tarah wizard 1 dafa chalayein ya 10 dafa, kabhi duplicate trips nahi bante.

---

### Q24: Do time ranges ke aapas me takrane (overlap) ka mathematical logic kya hai?
Golden formula:
$$\text{Overlap} \iff (\text{Start}_A < \text{End}_B) \land (\text{End}_A > \text{Start}_B)$$

```python
overlap_requests = self.env['logistics.transport.vehicle.request'].search([
    ('vehicle_id', '=', self.vehicle_id.id),
    ('id', '!=', self.id),
    ('state', 'in', ('approved', 'assigned')),
    ('date_from', '<', self.date_to),    # Start_A < End_B
    ('date_to', '>', self.date_from),    # End_A > Start_B
])
if overlap_requests:
    raise ValidationError(_("This vehicle is already booked for an overlapping time slot!"))
```
Agar yeh search koi record return kare to iska matlab booking conflict hai aur foran `ValidationError` raise ho jata hai.
