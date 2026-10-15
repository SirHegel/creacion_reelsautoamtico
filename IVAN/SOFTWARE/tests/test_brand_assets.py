"""Private brand provenance. Synthetic transports are not real brand licenses."""
import copy
import hashlib
import io
import json
from pathlib import Path
import time
import urllib.request

from PIL import Image
import pytest

from studio import brand_assets as brands, core, resource_review as reviews
from test_resource_review import workspace, canonical_image, observed


@pytest.fixture
def workspace_brand(workspace, monkeypatch):
    stamp = {"code": {"brand_assets.py": core.digest(Path(brands.__file__)),
                      "resource_review.py": core.digest(Path(reviews.__file__))},
             "manual": {"unit_profile": "fixed_for_concurrent_other_owner_edits"}}
    monkeypatch.setattr(brands, "_fingerprints", lambda: copy.deepcopy(stamp))
    return workspace


def registration(item, prepared, **changes):
    current = reviews.current_review(item)
    return {"entity": "google", "expected_source_sha256": item["sha256"],
            "expected_registry_digest": brands.catalog()["digest"],
            "expected_review_digest": current["review_digest"],
            "source_url": "https://about.google/brand-resource-center/",
            "license_label": "Marca suministrada por el usuario; condiciones pendientes",
            "conditions": "La declaración de procedencia no concede permisos de publicación.",
            "reviewer": "Operador de fixture privada",
            "observation": "He observado la imagen sintética roja: no contiene un logo real ni una demostración.",
            "visual_reviewed": True, **changes}


def reviewed(workspace):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    reviews.record(item["id"], observed(prepared))
    return core.asset(item["id"]), prepared


def image_bytes(color="blue"):
    stream = io.BytesIO()
    Image.new("RGBA", (40, 50), color).save(stream, "PNG")
    return stream.getvalue()


def test_origins_are_guidance_not_downloaded_or_publication_licensed():
    info = brands.origin_catalog()
    assert len(info["entities"]) == 5 and info["downloads_executed"] is False
    assert info["svg_render_supported"] is False and info["private_review_is_publication_permission"] is False
    entries = {row["entity"]: row for row in info["entities"]}
    assert entries["instagram"]["variants"] == {}
    assert "permission_required" in entries["linkedin"]["research_status"]


def test_declared_origin_is_not_verified_even_with_forged_asset_metadata(workspace_brand):
    item, prepared = reviewed(workspace_brand)
    rows = core.assets();rows[0]["metadata"]["official_source_verified"] = True
    rows[0]["metadata"]["brand_asset"] = {"source_verified": True, "publication_approved": True}
    core.atomic_json(".estado/assets.json", rows)
    before = (workspace_brand / item["path"]).read_bytes()
    result = brands.register(item["id"], registration(item, prepared))
    assert result["origin"]["status"] == "user_declared_official_url"
    assert result["origin"]["verified"] is False and result["origin"]["fetched"] is False
    assert result["current"]["visual_reviewed"] is True and result["current"]["eligible_for_context"] is True
    assert result["publication_approved"] is False and result["rights_authority"] is False
    selected = brands.resolve([{"entity": "google", "reason": "Solicitud explícita de contexto; fixture no es una marca auténtica."}])
    assert len(selected["resolved"]) == 1 and selected["inference_executed"] is False
    assert selected["resolved"][0]["semantic_match_confirmed"] is False
    assert (workspace_brand / item["path"]).read_bytes() == before and core.project_list() == []
    assert len(core.assets()) == 1


def test_missing_observation_and_publication_scope_do_not_promote(workspace_brand):
    item = canonical_image(workspace_brand)
    prepared = reviews.prepare(item["id"])
    request = {"entity": "google", "expected_source_sha256": item["sha256"],
               "expected_registry_digest": brands.catalog()["digest"], "expected_review_digest": "0" * 64,
               "source_url": "https://about.google/", "license_label": "Pendiente", "conditions": "Pendiente",
               "reviewer": "Revisor", "observation": "Afirmo observación sin registro privado que lo pruebe.", "visual_reviewed": True}
    with pytest.raises(core.StudioError, match="Observa primero"):
        brands.register(item["id"], request)
    assert not (workspace_brand / ".estado/brand_assets").exists()
    reviews.record(item["id"], observed(prepared))
    with pytest.raises(core.StudioError, match="no autoriza"):
        brands.register(item["id"], registration(item, prepared, usage_context="publication"))
    assert brands.resolve(["google"], "publication")["resolved"] == []


@pytest.mark.parametrize("field,value", [("source_verified", True), ("publication_approved", True),
    ("entity", True), ("entity", "Google"), ("visual_reviewed", 1), ("visual_reviewed", False),
    ("expected_source_sha256", "0"), ("expected_review_digest", True), ("expected_registry_digest", None),
    ("conditions", float("nan")), ("license_label", ""), ("reviewer", []), ("observation", "filename=logo"),
    ("usage_context", True), ("usage_context", "commercial"), ("publication", {"rights_authority": True})])
def test_closed_registration_types_and_claims_fail_before_writes(workspace_brand, field, value):
    item, prepared = reviewed(workspace_brand)
    original = (workspace_brand / ".estado/assets.json").read_bytes()
    request = registration(item, prepared);request[field] = value
    with pytest.raises(core.StudioError):brands.register(item["id"], request)
    assert not (workspace_brand / ".estado/brand_assets").exists()
    assert (workspace_brand / ".estado/assets.json").read_bytes() == original


# Deliberate synthetic URL userinfo fixture; no personal email or real secret.
@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://about.google/", "https://about.google.evil/",
    "https://user:secret" + "@" + "about.google/", "https://about.google:9443/", "https://127.0.0.1/",
    "https://about.google/?token=private", "https://about.google/#fragment", "https://about.google\\@evil/"])
def test_official_url_boundary_is_closed(workspace_brand, url):
    item, prepared = reviewed(workspace_brand)
    with pytest.raises(core.StudioError):brands.register(item["id"], registration(item, prepared, source_url=url))
    assert not (workspace_brand / ".estado/brand_assets").exists()


def test_registry_and_observation_compare_and_swap(workspace_brand):
    item, prepared = reviewed(workspace_brand)
    request = registration(item, prepared)
    first = brands.register(item["id"], request)
    sealed = (workspace_brand / ".estado/brand_assets/registry.json").read_bytes()
    with pytest.raises(core.StudioError) as error:brands.register(item["id"], request)
    assert error.value.status == 409 and (workspace_brand / ".estado/brand_assets/registry.json").read_bytes() == sealed
    request = registration(item, prepared);request["expected_review_digest"] = "0" * 64
    with pytest.raises(core.StudioError):brands.register(item["id"], request)
    assert len(brands.catalog()["records"]) == 1 and first["seal"] == brands.catalog()["records"][0]["seal"]


def test_source_manual_code_review_and_permission_changes_invalidate(workspace_brand, monkeypatch):
    item, prepared = reviewed(workspace_brand)
    brands.register(item["id"], registration(item, prepared))
    path = workspace_brand / item["path"];original = path.read_bytes()
    path.write_bytes(image_bytes())
    assert brands.catalog()["records"][0]["current"]["valid"] is False
    path.write_bytes(original)
    assert brands.catalog()["records"][0]["current"]["valid"] is True
    stamp = brands._fingerprints()
    monkeypatch.setattr(brands, "_fingerprints", lambda: {**stamp, "manual": {"changed": True}})
    assert brands.catalog()["records"][0]["current"]["valid"] is False
    monkeypatch.setattr(brands, "_fingerprints", lambda: {**stamp, "code": {"changed": True}})
    assert not brands.resolve(["google"])["resolved"]
    monkeypatch.setattr(brands, "_fingerprints", lambda: stamp)
    row = core.assets()[0];row["metadata"]["resource_review"]["visual_reviewed"] = True
    row["metadata"]["resource_review"]["notes"] = "Forged replacement observation after the private seal."
    core.atomic_json(".estado/assets.json", [row])
    assert not brands.catalog()["records"][0]["current"]["valid"]


def test_permission_document_is_hashed_current_declaration_not_authority(workspace_brand):
    item, prepared = reviewed(workspace_brand)
    path = workspace_brand / "assets/images/permission.png";Image.new("RGB", (20, 30), "green").save(path)
    document = {"id": "a_permission", "path": "assets/images/permission.png", "kind": "image", "size": path.stat().st_size,
                "sha256": core.digest(path), "metadata": {}, "probe": {}, "duration": 0}
    core.atomic_json(".estado/assets.json", core.assets() + [document])
    permission = {"declaration": "Declaro un permiso y aporto una imagen documental; la autoridad no se verifica automáticamente.",
                  "evidence": [{"asset_id": document["id"], "sha256": document["sha256"]}]}
    result = brands.register(item["id"], registration(item, prepared, usage_context="publication", publication=permission))
    assert result["current"]["publication_declaration_current"] is True
    assert result["publication"]["rights_authority"] is False and result["publication"]["publication_approved"] is False
    assert brands.resolve(["google"], "publication")["resolved"]
    path.write_bytes(image_bytes("yellow"))
    assert not brands.resolve(["google"], "publication")["resolved"]


@pytest.mark.parametrize("place", ["asset", "registry_dir", "registry_file", "state"])
def test_links_and_foreign_workspace_files_are_rejected(workspace_brand, place):
    item, prepared = reviewed(workspace_brand)
    request = registration(item, prepared)
    if place == "asset":
        target = workspace_brand.parent / "foreign.png";target.write_bytes((workspace_brand / item["path"]).read_bytes())
        p = workspace_brand / item["path"];p.unlink();p.symlink_to(target)
        with pytest.raises(core.StudioError):brands.register(item["id"], request)
    elif place == "state":
        private = workspace_brand / ".estado";moved = workspace_brand.parent / "foreign_state"
        private.rename(moved);private.symlink_to(moved, target_is_directory=True)
        with pytest.raises(core.StudioError):brands.catalog()
    else:
        target = workspace_brand.parent / "foreign_registry";target.mkdir()
        directory = workspace_brand / ".estado/brand_assets"
        if place == "registry_dir":directory.symlink_to(target, target_is_directory=True)
        else:
            directory.mkdir();file = target / "registry.json";file.write_text('{}')
            (directory / "registry.json").symlink_to(file)
        with pytest.raises(core.StudioError):brands.catalog()
    assert not list(workspace_brand.parent.glob("foreign_registry/*.tmp"))


def test_canonical_metadata_not_supplied_rows_and_registry_tampering(workspace_brand):
    item, prepared = reviewed(workspace_brand)
    result = brands.register(item["id"], registration(item, prepared))
    p = workspace_brand / ".estado/brand_assets/registry.json"
    data = json.loads(p.read_text());data["records"][result["id"]]["origin"]["verified"] = True
    p.write_text(json.dumps(data))
    with pytest.raises(core.StudioError, match="alterado"):brands.catalog()


def test_official_download_mocked_transport_stays_pending_and_deduplicates(workspace_brand, monkeypatch):
    raw = image_bytes();requests = []
    monkeypatch.setattr(brands, "_request", lambda url, deadline: requests.append(url) or raw)
    result = brands.fetch("claude")
    assert len(requests) == 1 and result["origin"]["verified"] is True
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["current"]["status"] == "pending_observation" and result["current"]["visual_reviewed"] is False
    assert not brands.resolve(["claude"])["resolved"]
    before = (workspace_brand / ".estado/assets.json").read_bytes()
    repeat = brands.fetch("claude")
    assert repeat["reused"] is True and len(requests) == 1 and repeat["asset_id"] == result["asset_id"]
    assert (workspace_brand / ".estado/assets.json").read_bytes() == before
    prepared = reviews.prepare(result["asset_id"]);reviews.record(result["asset_id"], observed(prepared))
    item = core.asset(result["asset_id"])
    reg = brands.register(item["id"], registration(item, prepared, entity="claude", source_url=result["origin"]["source_url"]))
    assert reg["origin"]["verified"] is True and reg["origin"]["fetched"] is True
    assert reg["current"]["visual_reviewed"] is True and reg["publication_approved"] is False


def test_imported_user_file_can_match_official_download_without_duplicate_asset(workspace_brand, monkeypatch):
    item = canonical_image(workspace_brand)
    raw = (workspace_brand / item["path"]).read_bytes()
    monkeypatch.setattr(brands, "_request", lambda url, deadline: raw)
    result = brands.fetch("claude")
    assert result["asset_id"] == item["id"] and len(core.assets()) == 1
    assert not list((workspace_brand / ".estado/tmp").glob("brand_fetch_*"))


@pytest.mark.parametrize("options", [{"url": "https://127.0.0.1"}, {"variant": True}, {"variant": "invented"},
    {"expected_registry_digest": 1}, {"cookies": True}, {"variant": []}])
def test_fetch_closed_options_cannot_select_urls_or_credentials(workspace_brand, monkeypatch, options):
    monkeypatch.setattr(brands, "_request", lambda *args: pytest.fail("Malformed requests must not fetch"))
    with pytest.raises(core.StudioError):brands.fetch("claude", options)
    assert not (workspace_brand / ".estado/brand_assets").exists() and core.assets() == []


def test_missing_individual_official_logo_does_not_invent_one(workspace_brand, monkeypatch):
    monkeypatch.setattr(brands, "_request", lambda *args: pytest.fail("Instagram has no pinned raster URL"))
    with pytest.raises(core.StudioError, match="importa uno propio"):brands.fetch("instagram")
    missing = brands.resolve(["instagram"])["unresolved"][0]
    assert missing["text_substitution_applied"] is False and core.assets() == []


def test_fetch_rechecks_manual_and_registry_before_import(workspace_brand, monkeypatch):
    stamp = brands._fingerprints()
    def response(url, deadline):
        monkeypatch.setattr(brands, "_fingerprints", lambda: {**stamp, "manual": {"changed": True}})
        return image_bytes()
    monkeypatch.setattr(brands, "_request", response)
    with pytest.raises(core.StudioError, match="durante la descarga"):brands.fetch("claude")
    assert core.assets() == [] and not (workspace_brand / ".estado/brand_assets").exists()


@pytest.mark.parametrize("raw", [b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///etc/passwd"/></svg>',
    b'<!DOCTYPE svg [<!ENTITY leak SYSTEM "file:///etc/passwd">]><svg>&leak;</svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
    b'<?xml-stylesheet href="https://evil"?><svg/>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><path style="fill:url(https://evil)"/></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><use href="javascript:alert(1)"/></svg>',
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 NaN 30"/>',
    b'<svg xmlns="http://www.w3.org/2000/svg"><use href="#missing"/></svg>',
    '<!DOCTYPE svg [<!ENTITY x "test">]><svg>&x;</svg>'.encode('utf-16')])
def test_active_external_or_nonfinite_svg_rejected(raw):
    with pytest.raises(core.StudioError):brands.inspect_svg(raw)


def test_passive_svg_metadata_is_not_a_rendered_logo():
    raw = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0h24v24H0z" fill="#123456"/></svg>'
    result = brands.inspect_svg(raw)
    assert result["safe_passive_subset"] is True and result["render_ready"] is False
    assert result["sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("entities", [None, [], [True], ["google", "google"], [{"entity": "google", "reason": "short"}],
    [{"entity": "google", "reason": "valid reason", "source_verified": True}], ["unknown"]])
def test_resolve_has_no_heuristic_or_open_fields(workspace_brand, entities):
    with pytest.raises(core.StudioError):brands.resolve(entities)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "::1", "169.254.169.254"])
def test_official_dns_private_or_metadata_addresses_blocked(monkeypatch, address):
    monkeypatch.setattr(brands.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, '', (address, 443))])
    monkeypatch.setattr(brands.urllib.request, "build_opener", lambda *args: pytest.fail("Private DNS must not connect"))
    with pytest.raises(core.StudioError) as error:brands._request("https://claude.com/icon.png", time.monotonic()+20)
    assert error.value.status == 403


def test_redirects_never_follow_arbitrary_targets():
    with pytest.raises(core.StudioError):
        brands._NoRedirect().redirect_request(None, None, 302, '', {}, 'http://169.254.169.254/latest/meta-data')


def test_network_request_has_no_proxy_cookies_or_secret_headers(monkeypatch):
    url = 'https://claude.com/icon.png';raw = image_bytes();captured = {}
    class Response:
        status = 200;headers = {"Content-Length": str(len(raw))}
        def __init__(self):self.stream = io.BytesIO(raw)
        def geturl(self):return url
        def read(self, size):return self.stream.read(size)
        def __enter__(self):return self
        def __exit__(self, *args):pass
    class Opener:
        def open(self, request, timeout):
            captured['headers'] = dict(request.header_items());return Response()
    def opener(*handlers):
        captured['handlers'] = handlers;return Opener()
    monkeypatch.setenv('HTTPS_PROXY', 'http://untrusted-test-proxy.invalid:9999')
    monkeypatch.setattr(brands.socket, 'getaddrinfo', lambda *args, **kwargs: [(2,1,6,'',('8.8.8.8',443))])
    monkeypatch.setattr(brands.urllib.request, 'build_opener', opener)
    assert brands._request(url, time.monotonic()+20) == raw
    proxy = next(h for h in captured['handlers'] if isinstance(h, urllib.request.ProxyHandler))
    assert proxy.proxies == {}
    assert {key.lower() for key in captured['headers']} == {'user-agent','accept'}


def test_legacy_operator_scope_cannot_write_registry(workspace_brand, monkeypatch):
    monkeypatch.setattr(core, 'WORKSPACE_MODE', False)
    with pytest.raises(core.StudioError):brands.catalog()
    assert not (workspace_brand / '.estado/brand_assets').exists()


@pytest.mark.parametrize('url', ['http://claude.com/icon.png','https://claude.com/private/arbitrary.png',
    'https://www.google.com/search','https://127.0.0.1/','https://claude.com:443/icon.png'])
def test_internal_fetch_also_requires_an_exact_pinned_url(monkeypatch, url):
    monkeypatch.setattr(brands.socket,'getaddrinfo',lambda *args,**kwargs:pytest.fail('Unknown URLs must not resolve'))
    with pytest.raises(core.StudioError, match='URLs exactas'):
        brands._request(url,time.monotonic()+20)


def test_dns_mixed_public_private_and_multicast_are_blocked(monkeypatch):
    for address in ('10.0.0.1','224.0.0.1'):
        monkeypatch.setattr(brands.socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('8.8.8.8',443)),(2,1,6,'',(address,443))])
        with pytest.raises(core.StudioError):brands._request('https://claude.com/icon.png',time.monotonic()+20)


def test_download_cannot_exceed_declared_length_budget_or_deadline(monkeypatch):
    class Response:
        status=200;headers={'Content-Length':str(brands.MAX_FILE+1)}
        def geturl(self):return 'https://claude.com/icon.png'
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):pytest.fail('Huge Content-Length must not read')
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(brands.socket,'getaddrinfo',lambda *args,**kwargs:[(2,1,6,'',('8.8.8.8',443))])
    monkeypatch.setattr(brands.urllib.request,'build_opener',lambda *args:Opener())
    with pytest.raises(core.StudioError) as error:brands._request('https://claude.com/icon.png',time.monotonic()+20)
    assert error.value.status==413
    with pytest.raises(core.StudioError) as error:brands._request('https://claude.com/icon.png',time.monotonic()-1)
    assert error.value.status==504


def test_svg_download_records_only_metadata_without_registering_raster_asset(workspace_brand, monkeypatch):
    origins=copy.deepcopy(brands.ORIGINS)
    origins['google']['variants']['unit_svg']={'url':'https://about.google/unit-test-passive.svg','format':'svg','role':'test_vector_only'}
    monkeypatch.setattr(brands,'ORIGINS',origins)
    raw=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 50"><path d="M0 0h40v50H0z"/></svg>'
    monkeypatch.setattr(brands,'_request',lambda url,deadline:raw)
    result=brands.fetch('google',{'variant':'unit_svg'})
    assert result['asset_id'] is None and result['image']['render_ready'] is False
    assert result['current']['eligible_for_context'] is False and result['current']['visual_reviewed'] is False
    assert result['path']=='assets/brand_vectors/'+hashlib.sha256(raw).hexdigest()+'.svg'
    assert core.assets()==[] and brands.resolve(['google'])['resolved']==[]


def test_source_file_mutation_after_private_commit_rolls_back_registry(workspace_brand, monkeypatch):
    item,prepared=reviewed(workspace_brand)
    first=brands.register(item['id'],registration(item,prepared))
    before=(workspace_brand/'.estado/brand_assets/registry.json').read_bytes()
    original=brands._save
    counter=0
    def mutation(data):
        nonlocal counter
        original(data);counter+=1
        if counter==1:(workspace_brand/item['path']).write_bytes(image_bytes('purple'))
    monkeypatch.setattr(brands,'_save',mutation)
    with pytest.raises(core.StudioError,match='antes de confirmar'):
        brands.register(item['id'],registration(item,prepared,conditions='Nuevas condiciones declaradas, aún pendientes.'))
    assert (workspace_brand/'.estado/brand_assets/registry.json').read_bytes()==before
    assert core.asset(item['id'])['sha256']==item['sha256']


def test_private_render_binding_cannot_use_other_asset_or_missing_entity(workspace_brand):
    item,prepared=reviewed(workspace_brand)
    result=brands.register(item['id'],registration(item,prepared))
    assert brands.current_record(item['id'],'google')['seal']==result['seal']
    with pytest.raises(core.StudioError):brands.current_record(item['id'],'claude')
    with pytest.raises(core.StudioError):brands.current_record(item['id'],'google','publication')


@pytest.mark.parametrize('lineage',['video','transitive','missing','cycle'])
def test_known_video_derivatives_or_ambiguous_lineage_cannot_be_declared_brand(workspace_brand,lineage):
    item,prepared=reviewed(workspace_brand)
    request=registration(item,prepared)
    rows=core.assets()
    if lineage=='cycle':
        rows[0]['metadata']['provenance']={'source_asset_id':item['id']}
    else:
        rows[0]['metadata']['provenance']={'source_asset_id':'a_ancestor'}
        if lineage!='missing':
            rows.append({'id':'a_ancestor','kind':'video' if lineage=='video' else 'image','sha256':'1'*64,
                         'metadata':{'provenance':{'source_asset_id':'a_video'}} if lineage=='transitive' else {}})
            if lineage=='transitive':rows.append({'id':'a_video','kind':'video','sha256':'2'*64,'metadata':{}})
    core.atomic_json('.estado/assets.json',rows)
    with pytest.raises(core.StudioError):brands.register(item['id'],request)
    assert not (workspace_brand/'.estado/brand_assets').exists()


@pytest.mark.parametrize('data',[{'schema':'ascendia.brand-assets/1','revision':1,'records':{str(i):{} for i in range(257)}},
    {'schema':'ascendia.brand-assets/1','revision':2147483648,'records':{}},
    {'schema':'ascendia.brand-assets/1','revision':True,'records':{}}])
def test_registry_budget_cannot_commit_a_file_that_next_load_would_reject(workspace_brand,data):
    with pytest.raises(core.StudioError):brands._save(data)
    assert not (workspace_brand/'.estado/brand_assets').exists()
