import json
import logging
import secrets
from pathlib import Path
from typing import Any

from app.core.clock import utcnow
from app.services import Services

log = logging.getLogger("unio.seed")

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
LAKH_PAISE = 10_000_000  # one lakh rupees, in paise

DEPARTMENTS = (
    {"_id": "D-CSE", "name": "Computer Science", "code": "CSE", "kind": "ACADEMIC"},
    {"_id": "D-ECE", "name": "Electronics & Communication", "code": "ECE", "kind": "ACADEMIC"},
    {"_id": "D-ELEC", "name": "Electrical Maintenance", "code": "ELEC", "kind": "FACILITY"},
    {"_id": "D-NET", "name": "Network Operations", "code": "NET", "kind": "FACILITY"},
)

# (id, name, email, role, department, one-tap demo chip, managed departments, approval limit in paise)
DEMO_USERS = (
    ("U-STUDENT", "Asha Nair", "student@unio.demo", "STUDENT", "D-CSE", True, (), 0),
    ("U-FACULTY", "Dr. Kiran Rao", "faculty@unio.demo", "FACULTY", "D-CSE", True, (), 0),
    ("U-DEPT", "Meera Iyer", "dept@unio.demo", "DEPARTMENT_MANAGER", "D-CSE", True, ("D-CSE",), LAKH_PAISE // 4),
    ("U-FACILITIES", "Arjun Menon", "facilities@unio.demo", "FACILITIES_ADMIN", "D-ELEC", True, (), LAKH_PAISE),
    ("U-PROCURE", "Divya Pillai", "procure@unio.demo", "PROCUREMENT_APPROVER", None, True, (), LAKH_PAISE * 10),
    ("U-TECH", "Ravi Kumar", "tech@unio.demo", "TECHNICIAN", "D-ELEC", True, (), 0),
    ("U-SYSADMIN", "Sam Thomas", "sysadmin@unio.demo", "SYSTEM_ADMIN", None, True, (), 0),
    # Second actors the demos depend on: self-approval, escalation and technician collisions.
    ("U-DEPT2", "Vikram Shetty", "dept2@unio.demo", "DEPARTMENT_MANAGER", "D-ECE", False, ("D-ECE",), LAKH_PAISE // 4),
    ("U-PROCURE2", "Nisha Varma", "procure2@unio.demo", "PROCUREMENT_APPROVER", None, False, (), LAKH_PAISE * 10),
    ("U-TECH2", "Meena Das", "tech2@unio.demo", "TECHNICIAN", "D-ELEC", False, (), 0),
    ("U-TECH3", "Joseph Paul", "tech3@unio.demo", "TECHNICIAN", "D-NET", False, (), 0),
    ("U-TECH4", "Lakshmi Bose", "tech4@unio.demo", "TECHNICIAN", "D-NET", False, (), 0),
)


async def _insert_if_missing(collection: Any, document: dict[str, Any]) -> None:
    """Never overwrites, so a restart cannot undo changes made at runtime."""
    await collection.update_one({"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True)


async def seed_roles(services: Services) -> None:
    now = utcnow()
    for role in json.loads((SEED_DIR / "roles.json").read_text(encoding="utf-8")):
        document = {
            "_id": role["key"],
            "label": role["label"],
            "workspace": role["workspace"],
            "accent": role["accent"],
            "permissions": role["permissions"],
            "scopes": role["scopes"],
            "version": 0,
            "createdAt": now,
        }
        await _insert_if_missing(services.db["roles_permissions"], document)
    await services.roles.refresh()


async def seed_demo_data(services: Services) -> None:
    settings = services.settings
    for department in DEPARTMENTS:
        await _insert_if_missing(services.db["departments"], dict(department))
    # With no password configured, one-tap sign-in still works but password sign-in does not.
    password = settings.demo_user_password or secrets.token_urlsafe(24)
    password_hash = await services.passwords.hash(password)
    now = utcnow()
    for user_id, name, email, role, department, demo_chip, managed, limit in DEMO_USERS:
        document = {
            "_id": user_id,
            "name": name,
            "email": email,
            "passwordHash": password_hash,
            "roleKey": role,
            "departmentId": department,
            "managedDepartmentIds": list(managed),
            "campusId": settings.campus_id,
            "approvalLimitPaise": limit,
            "procurementRequester": False,
            "demoAccount": demo_chip,
            "status": "ACTIVE",
            "lastLoginAt": None,
            "version": 0,
            "createdAt": now,
            "updatedAt": now,
        }
        await _insert_if_missing(services.db["users"], document)
    log.info("Demo accounts are ready")


async def seed_reference_data(services: Services) -> None:
    """Roles always seed, because the app cannot run without them. Demo users only in demo mode."""
    await seed_roles(services)
    if services.settings.demo_mode_enabled:
        await seed_demo_data(services)
