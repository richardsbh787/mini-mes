import math
from datetime import date, timedelta


# ==========================================================
# LINE CAPACITY SUMMARY + AUTO REBALANCE (A + B Version)
# ==========================================================

def calculate_line_capacity(
    production_line,
    work_orders,
    production_events,
    all_lines=None,
    all_work_orders=None,
    forecast_days: int = 5
):

    daily_capacity = (
        production_line.working_hours_per_day
        * production_line.efficiency_rate
    )

    if daily_capacity <= 0:
        return {"error": "Invalid daily capacity configuration"}

    # -------------------------------
    # OPEN / BLOCKED HOURS
    # -------------------------------
    open_orders = [
        wo for wo in work_orders
        if wo.status != "DONE" and wo.is_material_ready
    ]

    open_hours = sum(wo.remaining_hours for wo in open_orders)

    blocked_hours = sum(
        wo.remaining_hours
        for wo in work_orders
        if wo.status != "DONE" and not wo.is_material_ready
    )

    # -------------------------------
    # EVENT IMPACT
    # -------------------------------
    event_impact_hours = sum(
        event.impact_hours
        for event in production_events
        if not event.is_resolved
    )

    available_hours = daily_capacity * forecast_days
    net_available_hours = max(available_hours - event_impact_hours, 0)

    current_utilization = 0
    if net_available_hours > 0:
        current_utilization = open_hours / net_available_hours

    overload_gap_hours = 0
    escalation_required = False
    suggested_overtime = 0

    # -------------------------------
    # RISK ENGINE
    # -------------------------------
    if open_hours > net_available_hours:

        risk_level = "OVERLOAD"
        overload_gap_hours = open_hours - net_available_hours
        escalation_required = True

        suggested_overtime = math.ceil(
            overload_gap_hours / forecast_days
        )

        recommended_action = (
            f"Add {suggested_overtime} overtime hours per day "
            f"for next {forecast_days} days"
        )

    elif current_utilization >= 0.9:
        risk_level = "CRITICAL"
        recommended_action = "Prepare overtime or redistribute load"

    elif current_utilization >= 0.7:
        risk_level = "WARNING"
        recommended_action = "Monitor closely"

    else:
        risk_level = "SAFE"
        recommended_action = "Capacity healthy"

    # ==========================================================
    # AUTO REBALANCE ENGINE
    # ==========================================================

    auto_rebalance = None

    if risk_level == "OVERLOAD" and all_lines and all_work_orders:

        candidate_lines = []

        for line in all_lines:
            if line.id == production_line.id:
                continue

            line_orders = [
                wo for wo in all_work_orders
                if wo.production_line_id == line.id
                and wo.status != "DONE"
                and wo.is_material_ready
            ]

            line_open_hours = sum(wo.remaining_hours for wo in line_orders)

            line_daily_capacity = (
                line.working_hours_per_day * line.efficiency_rate
            )

            line_available = line_daily_capacity * forecast_days
            spare_capacity = line_available - line_open_hours

            if spare_capacity > 0:
                candidate_lines.append((line, spare_capacity))

        if candidate_lines:

            target_line, spare_capacity = max(
                candidate_lines,
                key=lambda x: x[1]
            )

            transfer_hours = min(overload_gap_hours, spare_capacity)

            priority_map = {"HIGH": 1, "NORMAL": 2, "LOW": 3}

            sorted_orders = sorted(
                open_orders,
                key=lambda x: (
                    priority_map.get(x.priority, 2),
                    x.promise_date
                ),
                reverse=True
            )

            selected_orders = []
            accumulated = 0

            for wo in sorted_orders:
                if accumulated >= transfer_hours:
                    break
                selected_orders.append(wo.work_order_no)
                accumulated += wo.remaining_hours

            auto_rebalance = {
                "suggested_line_id": target_line.id,
                "transfer_hours": round(transfer_hours, 2),
                "suggested_work_orders": selected_orders,
                "remaining_gap_after_transfer":
                    round(overload_gap_hours - transfer_hours, 2)
            }

    # ==========================================================

    return {
        "daily_capacity_hours": round(daily_capacity, 2),
        "forecast_days": forecast_days,
        "available_hours": round(available_hours, 2),
        "event_impact_hours": round(event_impact_hours, 2),
        "net_available_hours": round(net_available_hours, 2),
        "open_hours": round(open_hours, 2),
        "blocked_hours": round(blocked_hours, 2),
        "current_utilization": round(current_utilization, 2),
        "risk_level": risk_level,
        "overload_gap_hours": round(overload_gap_hours, 2),
        "escalation_required": escalation_required,
        "suggested_overtime_hours_per_day": suggested_overtime,
        "recommended_action": recommended_action,
        "auto_rebalance": auto_rebalance
    }


# ==========================================================
# LINE SIMULATION (完整版本)
# ==========================================================

def simulate_line_orders(production_line, work_orders, production_events):

    daily_capacity = (
        production_line.working_hours_per_day
        * production_line.efficiency_rate
    )

    if daily_capacity <= 0:
        return {"error": "Invalid daily capacity configuration"}

    open_orders = [
        wo for wo in work_orders
        if wo.status != "DONE" and wo.is_material_ready
    ]

    priority_map = {"HIGH": 1, "NORMAL": 2, "LOW": 3}

    sorted_orders = sorted(
        open_orders,
        key=lambda x: (
            priority_map.get(x.priority, 2),
            x.promise_date
        )
    )

    results = []
    accumulated_hours = 0
    today = date.today()

    for wo in sorted_orders:
        accumulated_hours += wo.remaining_hours

        days_needed = accumulated_hours / daily_capacity
        estimated_finish = today + timedelta(days=math.ceil(days_needed))

        delay_days = (estimated_finish - wo.promise_date).days
        will_delay = delay_days > 0

        results.append({
            "work_order_no": wo.work_order_no,
            "priority": wo.priority,
            "remaining_hours": wo.remaining_hours,
            "estimated_finish_date": estimated_finish,
            "promise_date": wo.promise_date,
            "delay_days": delay_days if delay_days > 0 else 0,
            "will_delay": will_delay,
            "status": "RUNNING"
        })

    return results
