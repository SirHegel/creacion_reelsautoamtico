"""Contratos externos y smoke de presentación opt-in; no modifica la biblioteca.

Ejecutar desde IVAN: python3 -B sistema/clone/test_presentation.py
Solo compila una fixture privada. El navegador funciona sin GPU ni render MP4.
"""
import json
import os
import pathlib
import signal
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import engine as e

TEMP = ".estado/tmp/clone_presentation"
REPORT = "proyectos/clone_motor/creatividad/presentation_qc.json"
PANEL_TITLE = "RESULTADOS POR CRITERIO"


def fixture():
    return {
        "schema_version": 1,
        "test_only": True,
        "scenes": [{
            "id": "presentation_probe",
            "family": "feedback_bars",
            "duration": 4,
            "content": "Tres observaciones sintéticas se organizan por criterio.",
            "objective": "Comprobar encaje y presentación, sin resultados auténticos.",
            "params": {
                "reviews": [
                    {"asset": "app_store", "text": "Resume textos cortos.", "tag": "PRUEBA"},
                    {"asset": "app_reddit", "text": "Ordena las respuestas.", "tag": "PRUEBA"},
                    {"asset": "app_g2", "text": "Devuelve un resumen.", "tag": "PRUEBA"},
                ],
                "categories": [
                    {"label": "Resumen", "value": 2, "color": "#d77357"},
                    {"label": "Orden", "value": 3, "color": "#e99b22"},
                    {"label": "Entrega", "value": 1, "color": "#ff3529"},
                ],
                "caption": "TRES CRITERIOS",
                "agent": "agent_entrepreneur",
            },
            "framing": {"view_box": [30, 40, 660, 1173.3333333333333]},
            "presentation": {"labels": {"panel_title": PANEL_TITLE}},
        }],
    }


def contract_tests(only=None):
    cases = []

    def reject(name, edit):
        if only is not None and name not in only:
            return
        spec = fixture()
        edit(spec["scenes"][0])
        try:
            e.validate_spec(spec)
        except ValueError as error:
            cases.append({"name": name, "pass": True, "rejected": True,
                          "error_type": "ValueError", "reason": str(error)})
        except Exception as error:
            cases.append({"name": name, "pass": False, "rejected": True,
                          "error_type": type(error).__name__, "reason": str(error),
                          "problem": "La entrada inválida debe producir ValueError de contrato."})
        else:
            cases.append({"name": name, "pass": False, "rejected": False})

    def framing(box):
        return lambda scene: scene.update(framing={"view_box": box})

    reject("framing_aspect_ratio", framing([0, 0, 720, 720]))
    reject("framing_right_outside", framing([1, 0, 720, 1280]))
    reject("framing_bottom_outside", framing([0, 1, 720, 1280]))
    reject("framing_negative_origin", framing([-1, 0, 720, 1280]))
    reject("framing_excessive_crop", framing([0, 0, 599, 1064.888888888889]))
    reject("framing_nan", framing([0, 0, float("nan"), 1280]))
    reject("framing_infinity", framing([0, 0, 720, float("inf")]))
    reject("framing_boolean", framing([False, 0, 720, 1280]))
    reject("framing_wrong_length", framing([0, 0, 720]))
    reject("framing_wrong_type", lambda scene: scene.update(framing="full"))
    reject("framing_extra_key", lambda scene: scene.update(
        framing={"view_box": [0, 0, 720, 1280], "zoom": 1}))
    reject("presentation_extra_key", lambda scene: scene.update(presentation={"html": "<b>title</b>"}))
    reject("presentation_wrong_type", lambda scene: scene.update(presentation=[]))
    reject("labels_unauthorized", lambda scene: scene.update(presentation={"labels": {"fake": "Title"}}))
    reject("labels_unsupported_family", lambda scene: scene.update(
        family="apps_clone_orbit", duration=4, params={},
        presentation={"labels": {"panel_title": "Title"}}))
    reject("labels_empty", lambda scene: scene.update(presentation={"labels": {"panel_title": "   "}}))
    reject("labels_excessive", lambda scene: scene.update(presentation={"labels": {"panel_title": "x" * 29}}))
    reject("labels_non_string", lambda scene: scene.update(presentation={"labels": {"panel_title": 3}}))
    reject("labels_wrong_type", lambda scene: scene.update(presentation={"labels": []}))
    reject("omit_illegal", lambda scene: scene.update(presentation={"omit": ["metric"]}))
    reject("omit_duplicate", lambda scene: scene.update(
        family="radial_research", params={}, presentation={"omit": ["metric", "metric"]}))
    reject("omit_wrong_type", lambda scene: scene.update(presentation={"omit": "metric"}))
    reject("omit_unhashable_dict", lambda scene: scene.update(presentation={"omit": [{}]}))
    reject("omit_unhashable_list", lambda scene: scene.update(presentation={"omit": [[]]}))
    reject("omit_non_string", lambda scene: scene.update(presentation={"omit": [False]}))

    positives = []
    for name, edit in ([] if only is not None else [
        ("opt_in_fixture", lambda scene: None),
        ("framing_full", framing([0, 0, 720, 1280])),
        ("without_presentation", lambda scene: scene.pop("presentation")),
        ("omit_declared_metric", lambda scene: scene.update(
            family="radial_research", params={}, presentation={"omit": ["metric"]})),
    ]):
        spec = fixture()
        edit(spec["scenes"][0])
        try:
            e.validate_spec(spec)
            positives.append({"name": name, "pass": True})
        except Exception as error:
            positives.append({"name": name, "pass": False, "reason": str(error)})
    return cases, positives


BROWSER_SMOKE = r"""
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
const ROOT=process.cwd(), TMP=path.join(ROOT,'.estado/tmp/clone_presentation');
const {chromium}=await import(pathToFileURL(path.join(ROOT,'.estado/herramientas/node_modules/playwright/index.mjs')).href);
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp/clone_presentation`;
process.env.XDG_CACHE_HOME=path.join(TMP,'cache');
process.env.XDG_CONFIG_HOME=path.join(TMP,'config');
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
const folder=path.join(TMP,'feedback_bars');
const phase=name=>fs.writeFileSync(path.join(TMP,'browser_phase.json'),JSON.stringify({phase:name,errors}));
const server=http.createServer((req,res)=>{
  const file=path.resolve(folder,'.'+new URL(req.url,'http://local').pathname);
  if(!file.startsWith(folder+'/')||!fs.existsSync(file)){res.writeHead(404).end();return;}
  res.writeHead(200,{'Content-Type':'text/html'});fs.createReadStream(file).pipe(res);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
let browser;
const errors=[];
try {
  phase('launching_browser');
  browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,
    timeout:20000,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-crash-reporter','--disable-breakpad','--force-color-profile=srgb']});
  phase('browser_open');
  const page=await browser.newPage({viewport:{width:720,height:1280}});
  page.on('pageerror',error=>{errors.push(error.message);phase('page_error');});
  phase('loading_fixture');
  const response=await page.goto(`http://127.0.0.1:${server.address().port}/index.html`,{waitUntil:'domcontentloaded',timeout:20000});
  phase('waiting_render_ready');
  await page.waitForFunction(()=>window.renderReady===true,null,{timeout:20000});
  phase('render_ready');
  const spec=JSON.parse(fs.readFileSync(path.join(folder,'scene.json'),'utf8'));
  const times=[0,.35,1,1.7,2.3,3.1,3.966666666666667];
  const snapshot=()=>page.evaluate(()=>[...document.querySelectorAll('svg [id],svg text')].map(n=>({
    id:n.id,text:n.tagName==='text'?n.textContent:null,
    transform:n.getAttribute('transform'),style:n.getAttribute('style'),size:n.getAttribute('font-size'),fill:n.getAttribute('fill')
  })));
  const seek=async t=>{
    phase('seek_'+t);
    // GSAP Timeline es thenable. No devolverla desde page.evaluate: al estar
    // pausada Playwright esperaría indefinidamente a que terminara.
    await page.evaluate(t=>{window.__timelines['clone-main'].seek(t,false);},t);
    phase('paint_'+t);
    // El reloj visual ya está fijado por seek. Screenshot fuerza la pintura;
    // no depender de RAF de una pestaña headless ocluida por otro navegador.
    await new Promise(resolve=>setTimeout(resolve,35));
    phase('screenshot_'+t);
    return await page.screenshot({timeout:15000});
  };
  const forward=[],backward=[];
  for(let i=0;i<times.length;i++){
    const png=await seek(times[i]);fs.writeFileSync(path.join(TMP,`forward_${i}.png`),png);
    forward.push({t:times[i],png:createHash('sha256').update(png).digest('hex'),dom:await snapshot()});
  }
  for(let i=times.length-1;i>=0;i--){
    const png=await seek(times[i]);fs.writeFileSync(path.join(TMP,`reverse_${i}.png`),png);
    backward.unshift({t:times[i],png:createHash('sha256').update(png).digest('hex'),dom:await snapshot()});
  }
  await seek(2.3);
  const probe=await page.evaluate(()=>{
    const root=document.querySelector('.scene-world'),svg=root.querySelector('svg');
    const title=[...svg.querySelectorAll('text')].find(n=>n.textContent==='RESULTADOS POR CRITERIO');
    const visible=n=>{
      for(let p=n;p&&p!==document.body;p=p.parentElement){const s=getComputedStyle(p);if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity)===0)return false;}
      const b=n.getBoundingClientRect();return b.width>0&&b.height>0;
    };
    const read=n=>({text:n.textContent,font_size:parseFloat(getComputedStyle(n).fontSize),visible:visible(n),bbox:n.getBoundingClientRect().toJSON()});
    const reviews=[0,1,2].map(i=>read(document.getElementById('presentation_probe-review'+i).querySelector('text')));
    const tags=[0,1,2].map(i=>read([...document.getElementById('presentation_probe-review'+i).querySelectorAll('rect')].at(-1)));
    const categories=[0,1,2].map(i=>read(document.getElementById('presentation_probe-row'+i).querySelector('text')));
    const review_tag_collisions=reviews.flatMap((r,i)=>{const a=r.bbox,b=tags[i].bbox;
      const width=Math.min(a.right,b.right)-Math.max(a.left,b.left),height=Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top);
      return width>1&&height>1?[{index:i,width,height,text:r.text}]:[];});
    return {gsap:gsap.version,fonts_ready:['700 30px Sequel','400 30px Scholar','400 30px InterUI','700 30px InterUI','400 30px Mono'].every(f=>document.fonts.check(f)),view_box:svg.getAttribute('viewBox').split(/\s+/).map(Number),title:title?read(title):null,reviews,categories,tags,review_tag_collisions,
      original_title_present:[...svg.querySelectorAll('text')].some(n=>n.textContent==='WHAT USERS WANT FIXED')};
  });
  const pairs=forward.map((x,i)=>({t:x.t,pixel_exact:x.png===backward[i].png,dom_exact:JSON.stringify(x.dom)===JSON.stringify(backward[i].dom),forward_png_sha256:x.png,reverse_png_sha256:backward[i].png}));
  const checks={http200:response.status()===200,no_browser_errors:errors.length===0,
    fonts_loaded:probe.fonts_ready,
    expected_framing:JSON.stringify(probe.view_box)===JSON.stringify(spec.scenes[0].framing.view_box),
    label_present_visible:!!probe.title?.visible,original_label_replaced:!probe.original_title_present,
    primary_reviews_over18:probe.reviews.every(n=>n.visible&&n.font_size>18),
    primary_categories_over18:probe.categories.every(n=>n.visible&&n.font_size>18),
    primary_reviews_clear_of_tags:probe.review_tag_collisions.length===0,
    reverse_seek_pixels_exact:pairs.every(p=>p.pixel_exact),reverse_seek_dom_exact:pairs.every(p=>p.dom_exact)};
  console.log(JSON.stringify({pass:Object.values(checks).every(Boolean),checks,probe,pairs,errors,
    limits:['Smoke software en navegador real de una fixture; no MP4 ni aprobación estética.','El título secundario tiene18px por contrato; se exige>18px al contenido principal.']}));
}finally{if(browser)await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
"""


def main():
    original_paths = [e.ROOT / "sistema/clone/components" / name for name in
                      ["agents.js", "devices.js", "research.js", "terminal.js", "proof_cards.js", "graph.js"]]
    original_paths += [e.ROOT / "ejemplos/clone_componente" / name for name in
                       ["diseno.svg", "clone_diseno_estatico.png", "clone_segmento_animado.mp4"]]
    before = {str(p.relative_to(e.ROOT)): e.digest(p) for p in original_paths}
    source_paths = [e.HERE / name for name in ["engine.py", "presentation.js", "presentation.json"]]
    source_before = {str(p.relative_to(e.ROOT)): e.digest(p) for p in source_paths}
    prior = e.load(REPORT, {}) if '--only-failed' in sys.argv else {}
    only = {x['name'] for x in prior.get('rejected_cases', []) if not x['pass']} if prior else None
    rejected, positives = contract_tests(only)
    if prior:
        refreshed = {x['name']: x for x in rejected}
        for value in refreshed.values():
            value['source_files_retested'] = source_before
        rejected = [refreshed.get(x['name'], x) for x in prior['rejected_cases']]
        positives = prior['positive_cases']
    temp = e.w.inside(TEMP)
    temp.mkdir(parents=True, exist_ok=True)
    browser_file = temp / "smoke.mjs"
    browser_file.write_text(BROWSER_SMOKE)
    smoke = {}
    try:
        e.compile_spec(fixture(), TEMP + "/feedback_bars")
        process = subprocess.Popen(["node", str(browser_file)], cwd=e.ROOT,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=65)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=5)
            raise RuntimeError('Browser smoke timed out; last phase: ' +
                               (temp / 'browser_phase.json').read_text())
        if process.returncode:
            smoke = {"pass": False, "error": stderr[-5000:], "returncode": process.returncode}
        else:
            smoke = json.loads(stdout)
    except Exception as error:
        smoke = {"pass": False, "error": str(error)}
    unchanged = all(e.digest(path) == expected for path, expected in before.items())
    source_stable = all(e.digest(path) == expected for path, expected in source_before.items())
    report = {
        "schema_version": 1, "fecha_utc": e.w.utc(),
        "test_file": "sistema/clone/test_presentation.py", "test_sha256": e.digest(__file__),
        "scope": "Contrato opt-in y navegador real; no render MP4, no cambios de biblioteca ni aprobación estética.",
        "source_files": source_before, "source_stable_during_test": source_stable,
        "contract_cases_retested": sorted(only) if only is not None else 'all',
        "retained_previous_contracts_source": prior.get('source_files') if prior else None,
        "rejected_cases": rejected, "positive_cases": positives, "browser_smoke": smoke,
        "base_immutable": {"pass": unchanged, "files": before},
        "pass": all(x["pass"] for x in rejected + positives) and smoke.get("pass", False) and unchanged and source_stable,
        "temporary_folder": TEMP,
    }
    e.write(REPORT, report)
    print(json.dumps({"report": REPORT, "pass": report["pass"],
                      "invalid_cases": len(rejected), "positive_cases": len(positives),
                      "failed_contracts": [x for x in rejected + positives if not x["pass"]],
                      "smoke": smoke.get("checks", smoke), "immutable": unchanged,
                      "source_stable": source_stable}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
