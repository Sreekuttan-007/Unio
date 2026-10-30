from datetime import UTC, datetime

from mongomock_motor import AsyncMongoMockClient

from app.core.authuser import AuthUser
from app.core.scope import DataScope, EntityType, match_nothing, scope_filter


def make_user(scopes: dict, managed: tuple[str, ...] = (), user_id: str = "U-1") -> AuthUser:
    return AuthUser(
        id=user_id,
        name="Test",
        email="t@unio.demo",
        role_key="X",
        campus_id="CAMPUS-1",
        department_id=None,
        managed_department_ids=managed,
        approval_limit_paise=0,
        permissions=frozenset(),
        scopes=scopes,
        token_id="jti",
        token_expires_at=datetime.now(UTC),
    )


def test_no_configured_scope_means_no_rows():
    assert scope_filter(make_user({}), EntityType.INCIDENT) == match_nothing()


def test_own_scope_matches_reporter_lists_and_owner_fields():
    user = make_user({EntityType.INCIDENT: DataScope.OWN, EntityType.BOOKING: DataScope.OWN})
    assert scope_filter(user, EntityType.INCIDENT) == {"reporterIds": "U-1"}
    assert scope_filter(user, EntityType.BOOKING) == {"requesterId": "U-1"}


def test_assigned_scope_reads_the_assignee_field_for_that_entity():
    user = make_user({EntityType.WORK_ORDER: DataScope.ASSIGNED, EntityType.INCIDENT: DataScope.ASSIGNED})
    assert scope_filter(user, EntityType.WORK_ORDER) == {"assignedUserId": "U-1"}
    assert scope_filter(user, EntityType.INCIDENT) == {"assignedUserIds": "U-1"}


def test_a_scope_with_no_meaning_for_the_entity_matches_nothing():
    user = make_user({EntityType.WORK_ORDER: DataScope.OWN})
    assert scope_filter(user, EntityType.WORK_ORDER) == match_nothing()


def test_department_scope_uses_managed_departments_and_fails_closed_without_any():
    managed = make_user({EntityType.INCIDENT: DataScope.DEPARTMENT}, managed=("D-CSE", "D-ECE"))
    assert scope_filter(managed, EntityType.INCIDENT) == {"departmentId": {"$in": ["D-CSE", "D-ECE"]}}
    none = make_user({EntityType.INCIDENT: DataScope.DEPARTMENT})
    assert scope_filter(none, EntityType.INCIDENT) == match_nothing()


def test_campus_and_system_scopes():
    assert scope_filter(make_user({EntityType.INCIDENT: DataScope.CAMPUS}), EntityType.INCIDENT) == {
        "campusId": "CAMPUS-1"
    }
    assert scope_filter(make_user({EntityType.AUDIT: DataScope.SYSTEM}), EntityType.AUDIT) == {}


def test_audit_scope_maps_to_domains_and_nothing_else():
    assert scope_filter(make_user({EntityType.AUDIT: DataScope.CAMPUS}), EntityType.AUDIT) == {"domain": "OPERATIONS"}
    assert scope_filter(make_user({EntityType.AUDIT: DataScope.PROCUREMENT}), EntityType.AUDIT) == {
        "domain": "PROCUREMENT"
    }
    assert scope_filter(make_user({EntityType.AUDIT: DataScope.OWN}), EntityType.AUDIT) == match_nothing()


async def test_filters_select_the_right_rows_in_the_database():
    incidents = AsyncMongoMockClient()["t"]["incidents"]
    await incidents.insert_many(
        [
            {"_id": "I1", "reporterIds": ["U-1", "U-2"], "departmentId": "D-CSE", "campusId": "CAMPUS-1"},
            {"_id": "I2", "reporterIds": ["U-3"], "departmentId": "D-CSE", "campusId": "CAMPUS-1"},
            {"_id": "I3", "reporterIds": ["U-4"], "departmentId": "D-ECE", "campusId": "CAMPUS-1"},
        ]
    )

    async def ids(user: AuthUser) -> list[str]:
        rows = await incidents.find(scope_filter(user, EntityType.INCIDENT)).to_list(length=10)
        return sorted(row["_id"] for row in rows)

    assert await ids(make_user({EntityType.INCIDENT: DataScope.OWN})) == ["I1"]
    assert await ids(make_user({EntityType.INCIDENT: DataScope.OWN}, user_id="U-2")) == ["I1"]
    assert await ids(make_user({EntityType.INCIDENT: DataScope.DEPARTMENT}, managed=("D-CSE",))) == ["I1", "I2"]
    assert await ids(make_user({EntityType.INCIDENT: DataScope.CAMPUS})) == ["I1", "I2", "I3"]
    assert await ids(make_user({})) == []
    assert await ids(make_user({EntityType.INCIDENT: DataScope.DEPARTMENT})) == []
