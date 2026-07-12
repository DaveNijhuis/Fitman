"""Verify _hash_password is defined once in auth.py, not duplicated in routers."""

import inspect

import routers.admin as admin_module
import routers.auth as auth_router_module


def test_hash_password_lives_in_auth():
    """auth.hash_password must be importable and produce a valid bcrypt hash."""
    from auth import hash_password, verify_password

    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert hashed.startswith("$2b$")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_auth_router_does_not_define_hash_password():
    """routers/auth.py must not define its own _hash_password."""
    assert not hasattr(auth_router_module, "_hash_password"), (
        "routers/auth.py still defines _hash_password — remove it and import from auth"
    )


def test_admin_does_not_define_hash_password():
    """routers/admin.py must not define its own _hash_password."""
    assert not hasattr(admin_module, "_hash_password"), (
        "routers/admin.py still defines _hash_password — remove it and import from auth"
    )


def test_routers_share_same_hash_function():
    """Both routers must use the same hash_password from auth, not separate copies."""
    from auth import hash_password

    # Both modules must reference the canonical function from auth
    auth_router_fn = getattr(auth_router_module, "hash_password", None)
    admin_fn = getattr(admin_module, "hash_password", None)

    assert auth_router_fn is hash_password, (
        "routers/auth.py does not import hash_password from auth"
    )
    assert admin_fn is hash_password, (
        "routers/admin.py does not import hash_password from auth"
    )


def test_hash_password_source_is_auth_module():
    """hash_password must be defined in auth.py, not in any router."""
    from auth import hash_password

    source_file = inspect.getfile(hash_password)
    assert source_file.endswith("auth.py") and "routers" not in source_file, (
        f"hash_password is defined in {source_file}, expected backend/auth.py"
    )
