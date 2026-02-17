from datetime import date


def calculate_work_order_risk(work_order):

    """
    Risk Engine V2
    Priority order:
    1. HOLD
    2. Overdue
    3. NPI
    4. Engineering Hold
    5. Safe
    """

    # 1️⃣ HOLD = 最高风险
    if str(work_order.status) == "WorkOrderStatus.HOLD" or str(work_order.status) == "HOLD":
        return {
            "overall_risk_level": "CRITICAL",
            "primary_constraint_type": "HOLD",
            "overall_delay_days": 0
        }

    # 2️⃣ 逾期
    if work_order.production_due_date < date.today():
        delay = (date.today() - work_order.production_due_date).days
        return {
            "overall_risk_level": "CRITICAL",
            "primary_constraint_type": "OVERDUE",
            "overall_delay_days": delay
        }

    # 3️⃣ 新产品
    if work_order.is_npi:
        return {
            "overall_risk_level": "RISK",
            "primary_constraint_type": "NPI",
            "overall_delay_days": 0
        }

    # 4️⃣ 工程暂停
    if work_order.engineering_hold:
        return {
            "overall_risk_level": "RISK",
            "primary_constraint_type": "ENGINEERING",
            "overall_delay_days": 0
        }

    # 5️⃣ 安全
    return {
        "overall_risk_level": "SAFE",
        "primary_constraint_type": None,
        "overall_delay_days": 0
    }
