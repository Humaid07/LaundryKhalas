"""Driver availability model + routing mode/cohort policy (Area A/B foundation)."""
from datetime import datetime

from services.routing import availability as av
from services.routing import config as cfg


def _drv(**over):
    base = {"active": True, "status": "free", "employment_status": "active",
            "shift_start": "08:00", "shift_end": "16:00", "express_eligible": False,
            "max_concurrent_assignments": 1, "active_assignment_count": 0}
    base.update(over)
    return base


T = datetime(2026, 8, 6, 12, 30)  # DEFAULT_SEED_TIME (Thu 12:30)


# ------------------------------ per-driver -------------------------------
def test_available_within_shift():
    assert av.compute_driver_availability(_drv(), T)["status"] == av.AVAILABLE


def test_not_yet_on_shift_before_start():
    r = av.compute_driver_availability(_drv(shift_start="14:00", shift_end="22:00"), T)
    assert r["status"] == av.NOT_YET_ON_SHIFT
    assert r["available"] is False and r["reason"] == "DRIVER_OUTSIDE_SHIFT"


def test_shift_ended_after_end():
    r = av.compute_driver_availability(_drv(shift_start="07:00", shift_end="11:00"), T)
    assert r["status"] == av.SHIFT_ENDED


def test_on_break_window():
    r = av.compute_driver_availability(_drv(break_start="12:00", break_end="13:00"), T)
    assert r["status"] == av.ON_BREAK and r["reason"] == "DRIVER_ON_BREAK"


def test_on_leave_window():
    r = av.compute_driver_availability(
        _drv(leave_start="2026-08-05T00:00", leave_end="2026-08-07T00:00"), T)
    assert r["status"] == av.ON_LEAVE and r["reason"] == "DRIVER_ON_LEAVE"


def test_offline_when_inactive_or_offline():
    assert av.compute_driver_availability(_drv(active=False), T)["status"] == av.OFFLINE
    assert av.compute_driver_availability(_drv(status="offline"), T)["status"] == av.OFFLINE


def test_assigned_at_limit():
    r = av.compute_driver_availability(_drv(active_assignment_count=1), T)
    assert r["status"] == av.ASSIGNED and r["reason"] == "DRIVER_ASSIGNMENT_LIMIT_REACHED"
    # below limit (max 2, count 1) -> still available
    r2 = av.compute_driver_availability(_drv(max_concurrent_assignments=2, active_assignment_count=1), T)
    assert r2["status"] == av.AVAILABLE


def test_express_available_requires_flag():
    assert av.compute_driver_availability(_drv(express_eligible=True), T)["express_available"] is True
    assert av.compute_driver_availability(_drv(express_eligible=False), T)["express_available"] is False


def test_precedence_offline_beats_shift():
    # offline wins even if within shift.
    assert av.compute_driver_availability(_drv(status="offline"), T)["status"] == av.OFFLINE


def test_service_days_not_scheduled_today():
    # only scheduled Sun(0)/Mon(1); Thu (mapped day 5) not scheduled.
    r = av.compute_driver_availability(_drv(service_days=[0, 1], shift_start="08:00", shift_end="16:00"), T)
    assert r["status"] == av.SHIFT_ENDED


# --------------------- three drivers != three available ------------------
def test_available_count_is_not_total_count():
    drivers = [
        _drv(),                                              # AVAILABLE
        _drv(shift_start="14:00", shift_end="22:00"),        # NOT_YET_ON_SHIFT
        _drv(status="on_leave"),                             # ON_LEAVE
    ]
    avs = [av.compute_driver_availability(d, T) for d in drivers]
    summary = av.summarize_drivers(avs)
    assert summary["total"] == 3
    assert summary["available"] == 1          # <-- the core spec requirement
    assert summary["outside_shift"] == 1
    assert summary["on_leave"] == 1


def test_three_drivers_zero_available():
    drivers = [_drv(status="offline"), _drv(status="on_break", break_start="12:00", break_end="13:00"),
               _drv(active_assignment_count=1)]
    avs = [av.compute_driver_availability(d, T) for d in drivers]
    assert av.summarize_drivers(avs)["available"] == 0


# ------------------------------- config ----------------------------------
class _S:
    def __init__(self, **k):
        self.__dict__.update(k)


def test_resolve_mode_off_when_disabled():
    assert cfg.resolve_mode(_S(advanced_routing_enabled=False, advanced_routing_mode="live")) == cfg.OFF
    assert cfg.resolve_mode(_S(advanced_routing_enabled=True, advanced_routing_mode="live")) == cfg.LIVE
    assert cfg.resolve_mode(_S(advanced_routing_enabled=True, advanced_routing_mode="bogus")) == cfg.OFF


def test_cohort_is_deterministic():
    a = cfg.cohort_bucket("order-123")
    assert a == cfg.cohort_bucket("order-123")  # stable across retries
    assert 0 <= a < 100


def test_should_run_advanced():
    live = _S(advanced_routing_enabled=True, advanced_routing_mode="live",
              allow_test_facility_routing=True)
    assert cfg.should_run_advanced(live, is_test=False) is True
    assert cfg.should_run_advanced(live, is_test=True) is True
    off = _S(advanced_routing_enabled=False, advanced_routing_mode="off",
             allow_test_facility_routing=True)
    assert cfg.should_run_advanced(off, is_test=False) is False
    shadow = _S(advanced_routing_enabled=True, advanced_routing_mode="shadow",
                allow_test_facility_routing=False)
    assert cfg.should_run_advanced(shadow, is_test=False) is True   # runs, not authoritative
    assert cfg.should_run_advanced(shadow, is_test=True) is False   # test routing not allowed


def test_authoritative_by_mode():
    shadow = _S(advanced_routing_enabled=True, advanced_routing_mode="shadow",
                allow_test_facility_routing=True, advanced_routing_canary_percentage=0)
    assert cfg.advanced_is_authoritative(shadow, is_test=False, order_id="o1") is False
    assert cfg.advanced_is_authoritative(shadow, is_test=True, order_id="o1") is True  # test never uses legacy
    live = _S(advanced_routing_enabled=True, advanced_routing_mode="live",
              allow_test_facility_routing=True, advanced_routing_canary_percentage=0)
    assert cfg.advanced_is_authoritative(live, is_test=False, order_id="o1") is True


def test_canary_cohort_stability():
    canary = _S(advanced_routing_enabled=True, advanced_routing_mode="canary",
                allow_test_facility_routing=True, advanced_routing_canary_percentage=100)
    # 100% canary -> everyone authoritative; and stable across calls (retries).
    assert cfg.advanced_is_authoritative(canary, is_test=False, order_id="o1") is True
    assert cfg.advanced_is_authoritative(canary, is_test=False, order_id="o1") is True
    canary0 = _S(advanced_routing_enabled=True, advanced_routing_mode="canary",
                 allow_test_facility_routing=True, advanced_routing_canary_percentage=0)
    assert cfg.advanced_is_authoritative(canary0, is_test=False, order_id="o1") is False
