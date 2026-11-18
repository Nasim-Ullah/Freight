# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Post-installation hook for trn_logistics_demo_data.

    Executes programmatic business workflows across trn_freight and
    trn_staff_transport (e.g. state transitions, trip generations).
    """
    _logger.info("Initializing PakLink Logistics Demo Data via post_init_hook...")

    # Assign PakLink company to Admin & Root users
    paklink = env.ref('trn_logistics_demo_data.company_paklink', raise_if_not_found=False)
    if paklink:
        for user_ref in ('base.user_admin', 'base.user_root'):
            user = env.ref(user_ref, raise_if_not_found=False)
            if user and paklink not in user.company_ids:
                user.write({'company_ids': [(4, paklink.id)]})
                _logger.info("Assigned PakLink company to %s", user_ref)

    # ========================================================
    # 1. Operational Freight Orders Lifecycle Transitions
    # ========================================================
    # Order 2: Submit
    order_2 = env.ref('trn_logistics_demo_data.order_02_submitted', raise_if_not_found=False)
    if order_2:
        try:
            order_2.action_submit()
            _logger.info("Order 2 successfully submitted.")
        except Exception as e:
            _logger.warning("Error submitting Order 2: %s", e)

    # Order 3: Confirm Clearance & Confirm Order (Reserves container)
    order_3 = env.ref('trn_logistics_demo_data.order_03_confirmed', raise_if_not_found=False)
    clearance_3 = env.ref('trn_logistics_demo_data.clearance_order_03', raise_if_not_found=False)
    if clearance_3:
        try:
            clearance_3.action_confirm()
        except Exception as e:
            _logger.warning("Error confirming clearance 3: %s", e)
    if order_3:
        try:
            order_3.action_submit()
            order_3.action_confirm()
            _logger.info("Order 3 successfully confirmed (Container reserved).")
        except Exception as e:
            _logger.warning("Error confirming Order 3: %s", e)

    # Order 4: Submit -> Confirm -> Invoice
    order_4 = env.ref('trn_logistics_demo_data.order_04_invoiced', raise_if_not_found=False)
    clearance_4 = env.ref('trn_logistics_demo_data.clearance_order_04', raise_if_not_found=False)
    if clearance_4:
        try:
            clearance_4.action_confirm()
        except Exception as e:
            _logger.warning("Error confirming clearance 4: %s", e)
    if order_4:
        try:
            order_4.action_submit()
            order_4.action_confirm()
            try:
                order_4.action_create_invoice()
                _logger.info("Order 4 successfully invoiced.")
            except Exception as inv_err:
                _logger.warning("Invoice creation in hook (Order 4): %s. Setting state to invoiced.", inv_err)
                order_4.state = 'invoiced'
        except Exception as e:
            _logger.warning("Error advancing Order 4: %s", e)

    # Order 5: Submit -> Confirm -> Invoice -> Done
    order_5 = env.ref('trn_logistics_demo_data.order_05_done', raise_if_not_found=False)
    clearance_5 = env.ref('trn_logistics_demo_data.clearance_order_05', raise_if_not_found=False)
    if clearance_5:
        try:
            clearance_5.action_confirm()
        except Exception as e:
            _logger.warning("Error confirming clearance 5: %s", e)
    if order_5:
        try:
            order_5.action_submit()
            order_5.action_confirm()
            try:
                order_5.action_create_invoice()
            except Exception as inv_err:
                _logger.warning("Invoice creation in hook (Order 5): %s. Setting state to invoiced.", inv_err)
                order_5.state = 'invoiced'
            if clearance_5:
                try:
                    clearance_5.action_done()
                except Exception as c_err:
                    _logger.warning("Error completing clearance 5: %s", c_err)
            order_5.action_done()
            _logger.info("Order 5 successfully completed (Done).")
        except Exception as e:
            _logger.warning("Error completing Order 5: %s", e)

    # Order 6: Submit -> Cancel (Releases container)
    order_6 = env.ref('trn_logistics_demo_data.order_06_cancelled', raise_if_not_found=False)
    if order_6:
        try:
            order_6.action_submit()
            order_6.action_cancel()
            _logger.info("Order 6 successfully cancelled.")
        except Exception as e:
            _logger.warning("Error cancelling Order 6: %s", e)

    # ========================================================
    # 2. Staff Transport Trips & Passenger Verification
    # ========================================================
    trip_1 = env.ref('trn_logistics_demo_data.trip_r01_completed', raise_if_not_found=False)
    if trip_1:
        try:
            trip_1._compute_passenger_metrics()
            _logger.info("Trip 1 metrics recomputed successfully.")
        except Exception as e:
            _logger.warning("Error computing Trip 1 metrics: %s", e)

    trip_2 = env.ref('trn_logistics_demo_data.trip_r02_in_progress', raise_if_not_found=False)
    if trip_2:
        try:
            trip_2._compute_passenger_metrics()
            _logger.info("Trip 2 metrics recomputed successfully.")
        except Exception as e:
            _logger.warning("Error computing Trip 2 metrics: %s", e)

