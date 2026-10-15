from pathlib import Path
import time

import pytest

from studio.accounts import Accounts, password_hash, password_matches
from studio.core import StudioError


@pytest.fixture
def accounts(tmp_path):
    return Accounts(tmp_path)


def user(email="ana@example.com",name="Ana"):
    return {"email":email,"name":name,"password":"Una contraseña privada 42"}


def test_password_salted_and_constant_format():
    one=password_hash(user()["password"]);two=password_hash(user()["password"])
    assert one!=two and one.startswith("scrypt$32768$8$3$")
    assert password_matches(user()["password"],one)
    assert not password_matches("otra contraseña larga",one)
    assert not password_matches("short",one)


def test_two_accounts_have_private_roots_and_only_own_tokens(accounts):
    a=accounts.register(user())["principal"]
    b=accounts.register(user("bea@example.com","Bea"))["principal"]
    assert accounts.workspace_path(a)!=accounts.workspace_path(b)
    token=accounts.create_token(a,{"name":"Codex propio"})
    assert accounts.authenticate(token["token"],agent=True)["workspace"]==a["workspace"]
    assert not accounts.tokens(b)
    with pytest.raises(StudioError) as error:accounts.revoke_token(b,token["id"])
    assert error.value.status==404
    assert accounts.revoke_token(a,token["id"])["revoked"]
    assert accounts.authenticate(token["token"],agent=True) is None


def test_session_logout_expiry_and_no_plaintext_credentials(accounts):
    result=accounts.register(user());secret=result["session"];principal=result["principal"]
    assert accounts.authenticate(secret)["user"]["email"]=="ana@example.com"
    assert accounts.authenticate(secret,agent=True) is None
    assert secret.encode() not in accounts.path.read_bytes()
    assert user()["password"].encode() not in accounts.path.read_bytes()
    assert accounts.path.stat().st_mode & 0o777==0o600
    accounts.logout(principal)
    assert accounts.authenticate(secret) is None
    login=accounts.login({k:user()[k] for k in ("email","password")})
    with accounts.connect() as db:db.execute("UPDATE sessions SET expires=?",(int(time.time())-1,))
    assert accounts.authenticate(login["session"]) is None


def test_casefold_login_duplicate_and_invalid_password(accounts):
    accounts.register(user("ANA@EXAMPLE.COM"))
    assert accounts.login({"email":"ana@example.com","password":user()["password"]})["principal"]["user"]["email"]=="ana@example.com"
    with pytest.raises(StudioError) as duplicate:accounts.register(user())
    assert duplicate.value.status==409
    with pytest.raises(StudioError) as error:accounts.login({"email":"ana@example.com","password":"invalid but long"})
    assert error.value.status==401


def test_login_limits_persist_and_unknown_account_has_same_error(accounts):
    for _ in range(10):
        with pytest.raises(StudioError) as error:accounts.login({"email":"none@example.com","password":"invalid but long"},"fixture")
        assert error.value.status==401
    with pytest.raises(StudioError) as limited:accounts.login({"email":"none@example.com","password":"invalid but long"},"fixture")
    assert limited.value.status==429


@pytest.mark.parametrize("field,value",[("email","bad"),("name",""),("password","short"),("password",None),("name","\x00")])
def test_invalid_registration_closed_schema(accounts,field,value):
    body=user();body[field]=value
    with pytest.raises(StudioError):accounts.register(body)
    with accounts.connect() as db:assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0


def test_account_symlink_rejected_before_any_write(tmp_path):
    root=tmp_path/"app";outside=tmp_path/"outside";root.mkdir();outside.mkdir()
    (root/".estado").symlink_to(outside,target_is_directory=True)
    with pytest.raises(StudioError):Accounts(root)
    assert list(outside.iterdir())==[]


def test_workspace_symlink_rejected_without_chmod_or_mutation(accounts,tmp_path):
    principal=accounts.register(user())["principal"]
    outside=tmp_path/"outside";outside.mkdir();before=outside.stat().st_mode
    base=accounts.root/"workspaces";base.mkdir()
    (base/principal["workspace"]["id"]).symlink_to(outside,target_is_directory=True)
    with pytest.raises(StudioError):accounts.workspace_path(principal)
    assert not list(outside.iterdir()) and outside.stat().st_mode==before


def test_agent_tokens_never_list_secret_or_allow_session_auth(accounts):
    principal=accounts.register(user())["principal"]
    token=accounts.create_token(principal,{"name":"Claude"})
    assert accounts.authenticate(token["token"]) is None
    assert "token" not in accounts.tokens(principal)[0]
    assert token["token"].encode() not in accounts.path.read_bytes()
    with accounts.connect() as db:db.execute("UPDATE agent_tokens SET expires=0")
    assert accounts.authenticate(token["token"],agent=True) is None
