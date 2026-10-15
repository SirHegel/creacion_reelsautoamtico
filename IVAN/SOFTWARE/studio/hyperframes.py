"""Local HyperFrames/GSAP adapter; every execution is isolated to SOFTWARE.

The installed CLI is a read-only executable dependency. Generated HTML uses
only schema-validated data, local resources and paused, registered timelines.
Successful execution is technical evidence, never an editorial approval.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import fcntl
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import tempfile
import time
import uuid

from PIL import Image, ImageDraw, ImageFont

from .core import StudioError
from . import render as native
from . import typography
from .runtime import CODE_ROOT, MANUAL_ROOT

ROOT = CODE_ROOT
VERSION = "1"
LOCK = threading.RLock()
LOADED_ADAPTER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EASES = {"linear": "none", "power1.inOut": "power1.inOut", "power2.out": "power2.out",
         "power2.inOut": "power2.inOut", "power3.out": "power3.out"}

# This preload is ours, not IVAN's workflow. Builtin named exports are synced
# before the CLI loads; workers inherit NODE_OPTIONS. No remote service or
# existing account configuration is used.
ISOLATOR = r'''import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import cp from 'node:child_process';
import http from 'node:http';
import https from 'node:https';
import net from 'node:net';
import {fileURLToPath} from 'node:url';
import {syncBuiltinESMExports} from 'node:module';
const root=process.env.ASCENDIA_HF_ROOT;
const home=process.env.ASCENDIA_HF_HOME;
const dependencies=process.env.ASCENDIA_HF_DEPENDENCIES;
if(!root||!home||!dependencies)throw new Error('Missing isolated HyperFrames scope');
const originalRealpath=fs.realpathSync.bind(fs);
const originalExists=fs.existsSync.bind(fs);
function stringPath(value){return value instanceof URL?fileURLToPath(value):Buffer.isBuffer(value)?value.toString():String(value);}
function resolved(value){
  let p=path.resolve(stringPath(value)),suffix=[];
  while(!originalExists(p)){suffix.unshift(path.basename(p));const parent=path.dirname(p);if(parent===p)break;p=parent;}
  try{p=originalRealpath(p);}catch{}
  return path.join(p,...suffix);
}
function inside(p,base){return p===base||p.startsWith(base+path.sep);}
function write(value){if(typeof value==='number')return;const p=resolved(value);if(!inside(p,root))throw new Error('Write outside SOFTWARE denied: '+p);}
function read(value){
  if(typeof value==='number')return;
  const p=resolved(value);
  if(inside(p,root)||inside(p,dependencies)||['/usr','/lib','/lib64','/bin','/proc','/dev','/sys/fs/cgroup','/etc/fonts','/etc/ld.so.cache'].some(base=>inside(p,base)))return;
  throw new Error('Read outside runtime scope denied: '+p);
}
for(const name of ['writeFile','appendFile','mkdir','mkdtemp','unlink','rmdir','rm','truncate','chmod','chown','utimes']){
  for(const target of [fs,fs.promises]){
    if(typeof target[name]==='function'){const original=target[name].bind(target);target[name]=function(value,...args){write(value);return original(value,...args);};}
  }
  const sync=name+'Sync';if(typeof fs[sync]==='function'){const original=fs[sync].bind(fs);fs[sync]=function(value,...args){write(value);return original(value,...args);};}
}
for(const name of ['rename','copyFile','cp','link','symlink']){
  for(const target of [fs,fs.promises])if(typeof target[name]==='function'){
    const original=target[name].bind(target);target[name]=function(a,b,...args){if(name==='rename'||name==='link'||name==='symlink')write(a);else read(a);write(b);return original(a,b,...args);};
  }
  const sync=name+'Sync';if(typeof fs[sync]==='function'){const original=fs[sync].bind(fs);fs[sync]=function(a,b,...args){if(name==='rename'||name==='link'||name==='symlink')write(a);else read(a);write(b);return original(a,b,...args);};}
}
function writable(flags){return typeof flags==='number'?Boolean(flags&(fs.constants.O_WRONLY|fs.constants.O_RDWR|fs.constants.O_CREAT|fs.constants.O_TRUNC|fs.constants.O_APPEND)):/[wa+]/.test(String(flags||'r'));}
for(const target of [fs,fs.promises])if(typeof target.open==='function'){
  const original=target.open.bind(target);target.open=function(value,flags,...args){(writable(flags)?write:read)(value);return original(value,flags,...args);};
}
const openSync=fs.openSync.bind(fs);fs.openSync=function(value,flags,...args){(writable(flags)?write:read)(value);return openSync(value,flags,...args);};
for(const name of ['readFile','readdir','stat','lstat','access']){
  for(const target of [fs,fs.promises])if(typeof target[name]==='function'){
    const original=target[name].bind(target);target[name]=function(value,...args){read(value);return original(value,...args);};
  }
  const sync=name+'Sync';if(typeof fs[sync]==='function'){const original=fs[sync].bind(fs);fs[sync]=function(value,...args){read(value);return original(value,...args);};}
}
for(const name of ['createReadStream','createWriteStream']){const original=fs[name].bind(fs);fs[name]=function(value,...args){(name==='createReadStream'?read:write)(value);return original(value,...args);};}
os.homedir=()=>home;
function local(url){const host=typeof url==='string'||url instanceof URL?new URL(url).hostname:url?.hostname||url?.host||'localhost';if(!['localhost','127.0.0.1','::1','[::1]'].includes(String(host).replace(/:\d+$/,'')))throw new Error('Remote network denied');}
for(const target of [http,https])for(const name of ['request','get']){const original=target[name].bind(target);target[name]=function(url,...args){local(url);return original(url,...args);};}
const fetch=globalThis.fetch;globalThis.fetch=function(url,...args){local(url);return fetch(url,...args);};
for(const name of ['connect','createConnection']){const original=net[name].bind(net);net[name]=function(...args){const value=args[0];if(typeof value==='object'&&!value.path)local(value);else if(typeof value==='number'&&typeof args[1]==='string')local({hostname:args[1]});return original(...args);};}
function command(file,args,options){
  args=[...(args||[])];options={...(options||{}),detached:false};
  if(options.cwd)write(options.cwd);
  const supplied=options.env||{};options.env={...process.env,...supplied};
  for(const key of ['NODE_OPTIONS','ASCENDIA_HF_ROOT','ASCENDIA_HF_HOME','ASCENDIA_HF_DEPENDENCIES','ASCENDIA_HF_TRACE','TMPDIR','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','HYPERFRAMES_NO_TELEMETRY','HYPERFRAMES_NO_UPDATE_CHECK','HYPERFRAMES_NO_AUTO_INSTALL','DO_NOT_TRACK','CUDA_VISIBLE_DEVICES'])if(process.env[key]!==undefined)options.env[key]=process.env[key];
  if(options.shell)throw new Error('Shell execution denied');
const name=path.basename(file);
  if(!/^(node|nodejs|ffmpeg|ffprobe|google-chrome|google-chrome-stable|chrome|chromium|chromium-browser|which|readlink|uname)$/.test(name))throw new Error('Executable outside isolated toolchain denied: '+name);
  if(/npm|npx|codex|nvidia-smi|curl|wget|python/.test(name))throw new Error('Unrelated executable denied: '+name);
  if(/ffmpeg|ffprobe/.test(name)){
    if(args.some(a=>/nvenc|cuda|qsv|vaapi|vulkan|hwaccel/.test(String(a))))throw new Error('GPU media processing denied');
    // FFmpeg's fast JPEG -> 8-bit planar RGB conversion in the installed
    // build leaves the final partial SIMD block black (360/1080: 8 columns).
    // Preserve geometry and the CLI's BT.601 -> RGB -> BT.709 conversion;
    // accurate full-chroma interpolation avoids that path. Match only this
    // exact, CLI-authored SDR screenshot chain, never arbitrary filters.
    const screenshotSdr='scale=in_color_matrix=bt601:in_range=pc:flags=neighbor,format=gbrp,scale=out_color_matrix=bt709:out_range=tv:flags=neighbor';
    if(name==='ffmpeg')args=args.map((a,i)=>i>0&&['-vf','-filter:v'].includes(args[i-1])&&a===screenshotSdr?a.replaceAll('flags=neighbor','flags=neighbor+full_chroma_int+accurate_rnd'):a);
    args=args.map((a,i)=>i>0&&['-threads','-filter_threads','-filter_complex_threads'].includes(args[i-1])?'2':a);
    args=['-threads','2',...(/ffmpeg/.test(name)?['-filter_threads','2','-filter_complex_threads','2','-protocol_whitelist','file,pipe,fd']:[]),...args];
    if(name.includes('ffmpeg')&&args.some(a=>a==='-i')&&args.length>1)args.splice(args.length-1,0,'-threads','2');
  }
  if(/chrome|chromium/.test(name)){
    args.push('--disable-background-networking','--disable-breakpad','--disable-crash-reporter','--disable-gpu','--renderer-process-limit=1');
  }
  if(process.env.ASCENDIA_HF_TRACE){write(process.env.ASCENDIA_HF_TRACE);fs.appendFileSync(process.env.ASCENDIA_HF_TRACE,JSON.stringify({type:'subprocess',file,args,cwd:options.cwd||process.cwd(),shell:false,detached:false})+'\n');}
  return [file,args,options];
}
for(const name of ['spawn','spawnSync','execFile','execFileSync']){
  const original=cp[name].bind(cp);cp[name]=function(file,args,options,...tail){
    if(!Array.isArray(args)){tail.unshift(options);options=args;args=[];}
    if(typeof options==='function'){tail.unshift(options);options={};}
    const adapted=command(file,args,options);return original(...adapted,...tail.filter(v=>v!==undefined));
  };
}
cp.execFile[Symbol.for('nodejs.util.promisify.custom')]=function(file,args,options){return new Promise((resolve,reject)=>{cp.execFile(file,args,options,(error,stdout,stderr)=>{if(error){error.stdout=stdout;error.stderr=stderr;reject(error);}else resolve({stdout,stderr});});});};
const originalFork=cp.fork.bind(cp);cp.fork=function(module,args,options){read(module);if(!Array.isArray(args)){options=args;args=[];}const [,adapted,scope]=command(options?.execPath||process.execPath,args,options);return originalFork(module,adapted,scope);};
for(const name of ['exec','execSync'])cp[name]=()=>{throw new Error('Shell execution denied');};
syncBuiltinESMExports();
if(process.env.ASCENDIA_HF_TRACE){write(process.env.ASCENDIA_HF_TRACE);fs.appendFileSync(process.env.ASCENDIA_HF_TRACE,JSON.stringify({type:'node',version:process.version,home:os.homedir(),cpu_allowed_list:fs.readFileSync('/proc/self/status','utf8').match(/^Cpus_allowed_list:\s*(.+)$/m)?.[1]||null})+'\n');}
'''


def _inside(root, value, exists=False):
    root = Path(root).resolve()
    if not root.is_relative_to(ROOT):
        raise StudioError("El adaptador debe permanecer dentro de SOFTWARE.", 403)
    path = Path(value)
    result = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not result.is_relative_to(root) or (exists and not result.is_file()):
        raise StudioError("Ruta del adaptador fuera de SOFTWARE o inexistente.", 403)
    return result


def _target(root, value):
    raw = Path(value) if Path(value).is_absolute() else Path(root) / value
    resolved = _inside(root, raw)
    if raw.absolute() != resolved or raw.is_symlink():
        raise StudioError("El adaptador no reemplaza enlaces simbólicos.", 403)
    return resolved


def _output_guard(root, output, cfg):
    sidecar = _target(root, output.with_suffix(".json"))
    protected = [item["local"] for item in cfg["assets"].values()] + [Path(cfg["primary"]), Path(cfg["accent"])]
    for destination in (output, sidecar):
        if any(destination == item or (destination.exists() and destination.samefile(item)) for item in protected):
            raise StudioError("El destino no puede reemplazar un original, recurso o fuente.",403)
    if sidecar.exists():
        try:
            previous = json.loads(sidecar.read_text())
            belongs = previous.get("path") == str(output.relative_to(root)) and output.is_file() and previous.get("sha256") == _sha(output)
        except (ValueError,OSError,TypeError):
            belongs = False
        if not belongs:
            raise StudioError("El recibo de destino ya existe y no pertenece a este exportado; no se reemplaza.",409)


def _sha(path):
    return native._hash(Path(path), "sha256")


def _json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _dependencies():
    local=CODE_ROOT / '.estado/herramientas/node_modules'
    packages = local if (local/'hyperframes/bin/hyperframes.mjs').is_file() else MANUAL_ROOT / ".estado/herramientas/node_modules"
    if packages.resolve()!=packages:
        raise StudioError('La carpeta del runtime HyperFrames debe ser real y local, sin alias.',403)
    dependencies={"packages": packages, "cli": packages / "hyperframes/bin/hyperframes.mjs",
            "cli_bundle":packages / "hyperframes/dist/cli.js",
            "cli_package": packages / "hyperframes/package.json", "gsap": packages / "gsap/dist/gsap.min.js",
            "path_plugin": packages / "gsap/dist/MotionPathPlugin.min.js", "gsap_package": packages / "gsap/package.json",
            "node": Path(shutil.which("node") or "/no-node"),
            "browser": Path(shutil.which("google-chrome") or shutil.which("chromium") or "/no-chrome"),
            "ffmpeg":Path(shutil.which("ffmpeg") or "/no-ffmpeg"),
            "ffprobe":Path(shutil.which("ffprobe") or "/no-ffprobe")}
    for key in ('cli','cli_bundle','cli_package','gsap','path_plugin','gsap_package'):
        if not dependencies[key].resolve().is_relative_to(packages):
            raise StudioError('Una dependencia HyperFrames sale de su instalación local autorizada.',403)
    return dependencies


def _executables(dependencies):
    tools = {key:dependencies[key] for key in ("node","browser")}
    tools.update(ffmpeg=dependencies["ffmpeg"],ffprobe=dependencies["ffprobe"])
    chrome = dependencies["browser"].resolve().parent / "chrome"
    if chrome.is_file():
        tools["browser_binary"] = chrome
    return {key:{"path":str(path.resolve()),"size":path.stat().st_size,"mtime_ns":path.stat().st_mtime_ns,"ctime_ns":path.stat().st_ctime_ns} for key,path in tools.items()}


def _cli_code(dependencies):
    digest = hashlib.sha256()
    directory = dependencies["cli"].parent.parent / "dist"
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix in {".js",".mjs"}:
            digest.update(str(path.relative_to(directory)).encode())
            digest.update(bytes.fromhex(_sha(path)))
    return digest.hexdigest()


def _installation(root=ROOT):
    """Installation facts only; callers need a fresh execution receipt."""
    _inside(root, ".")
    dependencies = _dependencies()
    required = ("cli", "cli_bundle", "cli_package", "gsap", "path_plugin", "gsap_package", "node", "browser", "ffmpeg", "ffprobe")
    missing = [key for key in required if not dependencies[key].is_file()]
    result = {"available": not missing, "missing": missing, "engine": "HyperFrames + GSAP", "verified_execution": False,
              "hardware_gpu": False, "browser_mode": "software", "workers": 1, "max_ffmpeg_threads": 2,
              "max_seconds": 7200, "preview_default_seconds": 10, "tested_duration": None,
              "editorial_approved": False, "scope": "SOFTWARE"}
    if not missing:
        cli = json.loads(dependencies["cli_package"].read_text())
        gsap = json.loads(dependencies["gsap_package"].read_text())
        result.update(cli_version=cli["version"], gsap_version=gsap["version"],
                      cli_license=cli.get("license"), gsap_license=gsap.get("license"),
                      adapter_sha256=_sha(__file__), runtime_sha256=_sha(dependencies["gsap"]),
                      cli_loader_sha256=_sha(dependencies["cli"]),
                      cli_bundle_sha256=_sha(dependencies["cli"].parent.parent / "dist/cli.js"),
                      cli_code_sha256=_cli_code(dependencies),executable_fingerprints=_executables(dependencies),
                      path_plugin_sha256=_sha(dependencies["path_plugin"]),
                      pixel_code_sha256={name:_sha(ROOT / "studio" / name) for name in ("hyperframes.py", "design.py", "render.py", "typography.py", "fonts.py")},
                      text_layout_runtime=typography.runtime_versions())
        result["module_current"] = result["adapter_sha256"] == LOADED_ADAPTER_SHA256
        if cli['version']!='0.8.147' or gsap['version']!='3.15.0':
            result.update(available=False,reason='El adaptador requiere las versiones verificadas HyperFrames0.8.147 y GSAP3.15.0; no actualiza ni mezcla instalaciones.')
    return result


def availability(root=ROOT):
    """Read-only installation facts plus a current, actual integration proof."""
    status = _installation(root)
    path = _inside(root, ".estado/hyperframes/integration.json")
    if status["available"] and path.is_file():
        try:
            receipt = json.loads(path.read_text())
            adapter = receipt["technical"]["hyperframes"]
            if not adapter.get("static_only") and adapter.get("dynamic_motion_verified") and verify_receipt(receipt,root):
                status.update(verified_execution=True,integration_path=str(path.relative_to(root)),integration_sha256=_sha(path),tested_duration=receipt.get("duration"))
        except (OSError, ValueError, KeyError, TypeError, StudioError):
            pass
    return status


def _runtime(root):
    status = _installation(root)
    if not status["available"]:
        raise StudioError("Faltan dependencias locales del adaptador: " + ", ".join(status["missing"]))
    if status.get("module_current") is not True:
        raise StudioError("El código del adaptador cambió: reinicia el proceso antes de ejecutar otra prueba.",409)
    dependencies = _dependencies()
    directory = _target(root, ".estado/hyperframes/runtime")
    directory.mkdir(parents=True, exist_ok=True)
    with LOCK:
        for key, name in (("gsap", "gsap.min.js"), ("path_plugin", "MotionPathPlugin.min.js")):
            target = _target(root, directory / name)
            if target.exists() and _sha(target) != _sha(dependencies[key]):
                raise StudioError("El runtime local cambió; no se sobrescribe.", 409)
            if not target.exists():
                shutil.copyfile(dependencies[key], target)
        guard = _target(root, directory / ("isolate_" + hashlib.sha256(ISOLATOR.encode()).hexdigest()[:16] + ".mjs"))
        if guard.exists() and guard.read_text() != ISOLATOR:
            raise StudioError("El aislador local cambió; no se sobrescribe.", 409)
        if not guard.exists():
            guard.write_text(ISOLATOR, encoding="utf-8")
        gsap_package = json.loads(dependencies["gsap_package"].read_text())
        _json(directory / "third_party.json", {"runtime": "GSAP", "version": status["gsap_version"],
              "license": status["gsap_license"], "source": gsap_package.get("repository"),
              "sha256": _sha(directory / "gsap.min.js"), "license_is_separate_from_editor": True})
    return directory, dependencies, status


def _environment(root, runtime, dependencies):
    home = _target(root, ".estado/hyperframes/home")
    temporary = _target(root, ".estado/hyperframes/tmp")
    home.mkdir(parents=True, exist_ok=True)
    temporary.mkdir(parents=True, exist_ok=True)
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "LD_LIBRARY_PATH") if key in os.environ}
    env.update(ASCENDIA_HF_ROOT=str(Path(root).resolve()), ASCENDIA_HF_HOME=str(home),
               ASCENDIA_HF_DEPENDENCIES=str(dependencies["packages"].resolve()),
               TMPDIR=str(temporary), XDG_CACHE_HOME=str(home / "cache"), XDG_CONFIG_HOME=str(home / "config"),
               XDG_DATA_HOME=str(home / "data"), PUPPETEER_CACHE_DIR=str(home / "browser"),
               NODE_OPTIONS="--import " + str(runtime / ("isolate_" + hashlib.sha256(ISOLATOR.encode()).hexdigest()[:16] + ".mjs")),
               HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1", HYPERFRAMES_NO_UPDATE_CHECK="1",
               HYPERFRAMES_NO_AUTO_INSTALL="1", HYPERFRAMES_SKIP_SKILLS="1", CI="1",
               HYPERFRAMES_BROWSER_PATH=str(dependencies["browser"]), PRODUCER_BROWSER_GPU_MODE="software",
               HYPERFRAMES_FFMPEG_PATH=native._tool("ffmpeg"), HYPERFRAMES_FFPROBE_PATH=native._tool("ffprobe"),
               CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", UV_THREADPOOL_SIZE="2")
    return env


def _cancelled(cancel):
    return native._cancelled(cancel)


def _guard_cancel(root, directory, cancel):
    if _cancelled(cancel):
        return True
    if shutil.disk_usage(directory).free < 512 * 1024 ** 2:
        raise StudioError("El render se detuvo para conservar espacio libre en el disco local.")
    return False


@contextmanager
def _execution_lock(root, cancel=None):
    path = _target(root, ".estado/hyperframes/render.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        while True:
            if _cancelled(cancel):
                raise StudioError("Adaptador cancelado.", 409)
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(.1)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _cli(root, directory, args, label, cancel=None, heartbeat=None, timeout=300):
    runtime, dependencies, status = _runtime(root)
    logs = _target(root, directory / "logs")
    logs.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = logs / (label + ".stdout"), logs / (label + ".stderr")
    command = [str(dependencies["node"]), str(dependencies["cli"]), *map(str, args)]
    nice = shutil.which("nice")
    if nice:
        command = [nice, "-n", "10", *command]
    affinity = sorted(os.sched_getaffinity(0))[:2] if hasattr(os, "sched_getaffinity") else None
    def scope_cpu():
        if affinity:
            os.sched_setaffinity(0, affinity)
    begin = time.monotonic()
    heartbeat_at = 0.
    disk_at = 0.
    environment = _environment(root, runtime, dependencies)
    trace_path = logs / (label + ".processes.jsonl")
    environment["ASCENDIA_HF_TRACE"] = str(trace_path)
    # Unix socket names have a 108-byte limit. This short descriptor alias
    # resolves to our real SOFTWARE temporary directory and stays open for
    # the whole child group; no /tmp or external symlink is created.
    temp_fd = os.open(environment["TMPDIR"], os.O_RDONLY | os.O_DIRECTORY)
    environment["TMPDIR"] = f"/proc/{os.getpid()}/fd/{temp_fd}"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        try:
            process = subprocess.Popen(command, cwd=directory, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       start_new_session=True, preexec_fn=scope_cpu if affinity else None)
        except BaseException:
            os.close(temp_fd)
            raise
        try:
            while process.poll() is None:
                if _cancelled(cancel):
                    raise StudioError("Adaptador cancelado.", 409)
                if time.monotonic() - begin > timeout:
                    raise StudioError("El comando HyperFrames superó su tiempo máximo.")
                if time.monotonic() - disk_at >= 1:
                    if shutil.disk_usage(directory).free < 512 * 1024 ** 2:
                        raise StudioError("El render se detuvo para conservar espacio libre en el disco local.")
                    disk_at = time.monotonic()
                if heartbeat and time.monotonic() - heartbeat_at >= 5:
                    heartbeat()
                    heartbeat_at = time.monotonic()
                time.sleep(.1)
            if process.returncode:
                detail = stdout_path.read_text(errors="replace")[-3200:] + stderr_path.read_text(errors="replace")[-1000:]
                raise StudioError(f"HyperFrames {label} falló: {detail}")
        finally:
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except OSError:
                        pass
                    process.wait(timeout=5)
            os.close(temp_fd)
    return {"stdout": stdout_path.read_text(errors="replace"), "stderr": stderr_path.read_text(errors="replace"),
            "seconds": round(time.monotonic() - begin, 3), "command": command[3:] if nice else command,
            "log_stdout": str(stdout_path.relative_to(root)), "log_stderr": str(stderr_path.relative_to(root)),
            "execution_trace":str(trace_path.relative_to(root))}


def _payload(text):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
    raise StudioError("HyperFrames no devolvió un recibo JSON válido.")


def _execution_proof(root, directory, commands, require_encoder=True, cancel=None):
    """Observed executable versions and enforced subprocess flags, not intent."""
    traces = []
    for command in commands:
        path = _inside(root, command["execution_trace"], True)
        if path.stat().st_size > 16 * 1024 ** 2:
            raise StudioError("El recibo de ejecución del adaptador excede el límite local.")
        traces.extend(json.loads(line) for line in path.read_text().splitlines() if line)
    nodes = [item for item in traces if item.get("type") == "node"]
    browser = [item for item in traces if item.get("type") == "subprocess" and re.search(r"chrome|chromium",Path(item["file"]).name)]
    media = [item for item in traces if item.get("type") == "subprocess" and "ffmpeg" in Path(item["file"]).name]
    if not nodes or not browser or (require_encoder and not media):
        raise StudioError("Falta evidencia de ejecución real del navegador o codificador.")
    for item in browser:
        if "--disable-gpu" not in item["args"] or "--renderer-process-limit=1" not in item["args"]:
            raise StudioError("El navegador no respetó el perfil de CPU aislado.")
    for item in media:
        args = item["args"]
        if not any(value == "-threads" for value in args):
            raise StudioError("El codificador no registró su límite de hilos.")
        for index,value in enumerate(args[:-1]):
            if value in {"-threads","-filter_threads","-filter_complex_threads"} and int(args[index+1]) > 2:
                raise StudioError("El codificador excedió dos hilos.")
    dependencies = _dependencies()
    runtime,_,_= _runtime(root)
    env = _environment(root,runtime,dependencies)
    versions = {"node":nodes[0]["version"]}
    for key in ("browser","ffmpeg","ffprobe"):
        if _cancelled(cancel):
            raise StudioError("Adaptador cancelado.",409)
        args = [str(dependencies[key]),"--version" if key=="browser" else "-version"]
        if key == "browser":
            args.extend(["--disable-gpu","--disable-background-networking","--user-data-dir="+str(_target(root,".estado/hyperframes/home/version-profile"))])
        if shutil.which("nice"):
            args = [shutil.which("nice"),"-n","10",*args]
        completed = subprocess.run(args,cwd=directory,env=env,shell=False,stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,check=True)
        lines = completed.stdout.decode("utf8","replace").splitlines()
        if not lines:
            raise StudioError("No se pudo verificar la versión real de "+key+".")
        versions[key]=lines[0]
    path = directory / "execution.json"
    _json(path,{"versions":versions,"node_cpu_allowed_lists":sorted({item.get("cpu_allowed_list") for item in nodes}),
                "observed_browser_processes":len(browser),"observed_encoder_processes":len(media),
                "hardware_gpu":False,"max_ffmpeg_threads":2,"scope":"SOFTWARE"})
    return {"path":str(path.relative_to(root)),"versions":versions,
            "trace_paths":[item["execution_trace"] for item in commands]}


def _number(value):
    value = float(value)
    if not math.isfinite(value):
        raise StudioError("La composición contiene un número no finito.")
    return format(value, ".12g")


def _js(value):
    # Even text containing </script> remains data, never executable markup.
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _font_identity(cfg, root):
    profile = cfg.get("branding")
    if profile is not None:
        from .fonts import inspect_font
        if profile.get("font_override_explicit") is not True or profile.get("base") != "ivan_yo_clone":
            raise StudioError("La identidad tipográfica requiere una marca explícita verificada.", 409)
        for role in ("primary", "accent"):
            face = profile["fonts"][role]
            path = _inside(root, cfg[role], True)
            actual = inspect_font(path, root)
            if path != _inside(root, face["path"], True) or any(actual.get(key) != face.get(key) for key in ("sha256", "family", "style")):
                raise StudioError("La fuente real ya no coincide con la marca protegida del proyecto.", 409)
        return
    for key, family, style in (("primary", "Sequel Sans", "Bold"), ("accent", "Scholar", "Italic")):
        path = _inside(root, cfg[key], exists=True)
        if not path.is_relative_to(Path(root).resolve() / "assets" / "fonts"):
            raise StudioError("Las fuentes auténticas deben permanecer en assets/fonts.")
        actual_family, actual_style = ImageFont.truetype(str(path), 24).getname()
        compact = re.sub(r"[^a-z]", "", actual_family.lower())
        actual = re.sub(r"[^a-z]", "", (actual_family + actual_style).lower())
        if re.sub(r"[^a-z]", "", family.lower()) not in compact or style.lower() not in actual or (key == "primary" and "disp" not in actual):
            raise StudioError("El adaptador requiere Sequel Sans Bold Disp y Scholar Italic reales.")


def _split_camera(cfg, scene, root, directory, cancel):
    """Stage only the authentic lower camera region, without voice duplication."""
    w, h, fps = cfg["width"], cfg["height"], cfg["fps"]
    shape = (w, h - cfg['split_height'])
    span = scene["end"] - scene["start"]
    count = max(1, math.ceil(span * fps - 1e-8))
    entry = scene.get("source_in", scene["start"])
    temporary = _inside(root, ".estado/tmp")
    temporary.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="split_camera_", dir=temporary) as folder:
        raw, encoded = Path(folder) / "camera.rgb", Path(folder) / "camera.mp4"
        native._decode(cfg["source"], shape, entry, count, fps, raw, root, scene, cancel)
        native._run([native._tool("ffmpeg"), "-v", "error", "-n", "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{shape[0]}x{shape[1]}", "-framerate", str(fps), "-i", str(raw), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "2", str(encoded)], root, cancel)
        name = "media/" + _sha(encoded) + ".mp4"
        _copy_resource(root, directory, encoded, name)
    return {"url": name, "image": False}


def _ease(frame):
    name = EASES[frame.get("ease", "linear")]
    window = frame.get("ease_window", [0, 1])
    if window == [0, 1]:
        return _js(name)
    lo, hi = map(_number, window)
    return f"(u=>{{const e=gsap.parseEase({_js(name)}),a=e({lo}),b=e({hi});return Math.abs(b-a)<1e-12?u:(e({lo}+({hi}-{lo})*u)-a)/(b-a);}})"


def _mask(element, progress, width, height):
    mask = element.get("mask", {})
    if mask.get("type") == "circle":
        return f"circle({_number(min(width, height) * .5 * progress)}px at 50% 50%)"
    if mask.get("type") == "inset":
        sides = mask.get("inset", {})
        left, right = sides.get("left", 0), sides.get("right", 0)
        right += (1 - left - right) * (1 - progress)
        return "inset(" + " ".join(_number(100 * value) + "%" for value in (sides.get("top", 0), right, sides.get("bottom", 0), left)) + ")"
    return "none"


def _animate_element(selector, inner, element, scene_duration, width, height, legacy=False):
    """Numeric schema -> explicit safe GSAP properties; no user JS or SVG."""
    channels = ("x", "y", "scale", "opacity", "rotation", "mask_progress")
    base = {"x": element.get("x", 0), "y": element.get("y", 0), "scale": 1,
            "opacity": element.get("opacity", 1), "rotation": element.get("rotation", 0),
            "mask_progress": element.get("mask_progress", 1)}
    poses = [(0., base.copy(), {})]
    frames = sorted(element.get("keyframes", []), key=lambda f: f["time"])
    if legacy and frames:
        first = {**base, **{key:frames[0].get(key,base[key]) for key in channels}}
        poses = [(0.,first,{})]
    for frame in frames:
        if legacy:
            frame = {**frame, **{key:frame.get(key,base[key]) for key in channels}}
        state = {**poses[-1][1], **{key: frame[key] for key in channels if key in frame}}
        item = (float(frame["time"]), state, frame)
        if item[0] == poses[-1][0]:
            poses[-1] = item
        else:
            poses.append(item)
    path = element.get("path")
    def properties(state):
        result = {key: state[key] for key in ("scale", "opacity", "rotation")}
        if not path:
            result.update(x=state["x"] * width, y=state["y"] * height)
        return result
    code = [f"gsap.set({_js(selector)},{_js(properties(poses[0][1]))});"]
    bw, bh = element.get("width", .25) * width, element.get("height", .25) * height
    if element.get("mask", {}).get("type", "none") != "none":
        code.append(f"gsap.set({_js(inner)},{{clipPath:{_js(_mask(element, poses[0][1]['mask_progress'], bw, bh))}}});")
    for before, after in zip(poses, poses[1:]):
        at, state, frame = after
        duration = at - before[0]
        props = _js(properties(state))[:-1]
        easing = "(u=>u*u*(3-2*u))" if legacy else _ease(frame)
        code.append(f"tl.to({_js(selector)},{props},duration:{_number(duration)},ease:{easing} }},{_number(before[0])});")
        if element.get("mask", {}).get("type", "none") != "none":
            code.append(f"tl.to({_js(inner)},{{clipPath:{_js(_mask(element, state['mask_progress'], bw, bh))},duration:{_number(duration)},ease:{_ease(frame)}}},{_number(before[0])});")
    if path:
        points = path["points"]
        length = [math.hypot((b["x"] - a["x"]) * width, (b["y"] - a["y"]) * height) for a, b in zip(points, points[1:])]
        total = sum(length)
        start, end = element.get("start", 0), element.get("end", scene_duration)
        code.append(f"gsap.set({_js(selector)},{{x:{_number(points[0]['x'] * width)},y:{_number(points[0]['y'] * height)}}});")
        at = start
        for point, distance in zip(points[1:], length):
            if total == 0 or distance == 0:
                continue
            duration = (end - start) * distance / total
            code.append(f"tl.to({_js(selector)},{{x:{_number(point['x'] * width)},y:{_number(point['y'] * height)},duration:{_number(duration)},ease:'none'}},{_number(at)});")
            at += duration
    return "\n".join(code)


def _text_ease(name, lo, hi):
    formulas = {"linear": "v", "out3": "1-Math.pow(1-v,3)", "out4": "1-Math.pow(1-v,4)",
                "inout3": "v<.5?4*v*v*v:1-4*Math.pow(1-v,3)"}
    expression = formulas[name]
    return f"(u=>{{const e=v=>({expression}),a=e({_number(lo)}),b=e({_number(hi)});return Math.abs(b-a)<1e-12?u:(e({_number(lo)}+({_number(hi-lo)})*u)-a)/(b-a);}})"


def _text_svg(layout, element, dom_id, family, scene_duration):
    """Measured SVG text nodes: no project SVG/HTML or implicit font capture."""
    style, k = layout["style"], layout["reference_scale"]
    shadow, stroke = style["shadow"], style["stroke"]
    initial = typography.animation_state(element, 0, scene_duration)
    spacing = style["letter_spacing"]
    nodes, selectors = [], {}
    groups = [("fg", layout["color"], 1)]
    if shadow["enabled"] and shadow["opacity"]:
        groups.insert(0, ("sh", shadow["color"], shadow["opacity"]))
    filter_id = dom_id + "_shadow_filter"
    if shadow["blur"]:
        nodes.append(f'<defs><filter id="{filter_id}" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="{_number(shadow["blur"]*k)}"/></filter></defs>')
    for role, color, opacity in groups:
        # These nodes paint the same glyphs as a decorative shadow, not a
        # second text block. Keep the waiver on each shadow node: it is not
        # inherited, and foreground/independent text still gets audited.
        decoration = ' aria-hidden="true" data-layout-allow-overlap' if role == "sh" else ""
        transform = f' transform="translate({_number(shadow["x"]*k)} {_number(shadow["y"]*k)})"' if role == "sh" else ""
        filter_attribute = f' filter="url(#{filter_id})"' if role == "sh" and shadow["blur"] else ""
        stroke_color = color if role == "sh" else stroke["color"]
        nodes.append(f'<g fill="{color}" opacity="{_number(opacity)}" stroke="{stroke_color}" stroke-width="{_number(stroke["width"]*k*2)}" paint-order="stroke fill"{transform}{filter_attribute}>')
        for index, line in enumerate(layout["lines"]):
            if spacing == 0:
                node_id = f"{dom_id}_{role}_line_{index}"
                selectors.setdefault(("line", index), []).append("#"+node_id)
                prefix = typography.line_prefix(line, initial, layout)
                nodes.append(f'<text id="{node_id}" x="{_number(line["x"])}" y="{_number(line["baseline"])}"{decoration} xml:space="preserve">{html.escape(prefix)}</text>')
            else:
                for unit in line["units"]:
                    node_id = f"{dom_id}_{role}_unit_{unit['index']}"
                    selectors.setdefault(("unit", unit["index"]), []).append("#"+node_id)
                    mode = initial["reveal_mode"]
                    count = layout["grapheme_count"] if mode == "grapheme" else layout["word_count"]
                    visible = count if initial["reveal_fraction"] >= 1 else math.floor(count*initial["reveal_fraction"]+1e-10)
                    show = mode == "none" or (unit["index"] < visible if mode == "grapheme" else unit["word_index"] < visible)
                    nodes.append(f'<text id="{node_id}" x="{_number(unit["x"])}" y="{_number(line["baseline"])}" opacity="{1 if show else 0}"{decoration} xml:space="preserve">{html.escape(unit["text"])}</text>')
        nodes.append("</g>")
    svg = (f'<svg width="100%" height="100%" viewBox="0 0 {layout["width"]} {layout["height"]}" '
           f'style="display:block;overflow:hidden;font-family:{family};font-size:{layout["font_px"]}px;font-weight:400;font-style:normal;font-synthesis:none;white-space:pre;">' + "".join(nodes) + "</svg>")
    content = f'<div id="{dom_id}_text_alpha" style="position:absolute;inset:0;"><div id="{dom_id}_text_move" style="position:absolute;inset:0;transform-origin:50% 50%;"><div id="{dom_id}_text_wipe" style="position:absolute;inset:0;">{svg}</div></div></div>'
    return content, selectors


def _animate_text(element, layout, dom_id, selectors, scene_duration):
    animation = typography.normalize_animation(element, scene_duration)
    state = typography.animation_state(element, 0, scene_duration)
    scale = layout["reference_scale"]
    move, alpha, wipe = "#"+dom_id+"_text_move", "#"+dom_id+"_text_alpha", "#"+dom_id+"_text_wipe"
    code = [f"gsap.set({_js(move)},{_js({'x':state['x']*scale,'y':state['y']*scale,'scale':state['scale']})});",
            f"gsap.set({_js(alpha)},{{opacity:{_number(state['opacity'])}}});",
            f"gsap.set({_js(wipe)},{{clipPath:{_js('inset(0 '+_number((1-state['wipe'])*100)+'% 0 0)')}}});"]
    began = animation["clock_start"]-animation["clock_offset"]
    preset = animation["preset"]
    duration = animation["duration"]
    left, right = max(0.,began), min(scene_duration,began+duration)
    if preset != "none" and right > left:
        lo,hi=(left-began)/duration,(right-began)/duration
        endstate=typography.animation_state(element,right,scene_duration)
        if preset in ("fade_up","slide","pop"):
            channel = "y" if preset=="fade_up" else "x" if preset=="slide" else "scale"
            value=endstate[channel]*(1 if channel=="scale" else scale)
            code.append(f"tl.to({_js(move)},{{{channel}:{_number(value)},duration:{_number(right-left)},ease:{_text_ease('out4' if preset=='pop' else 'out3',lo,hi)}}},{_number(left)});")
            code.append(f"tl.to({_js(alpha)},{{opacity:{_number(hi)},duration:{_number(right-left)},ease:'none'}},{_number(left)});")
        elif preset=="wipe":
            clip='inset(0 '+_number((1-hi)*100)+'% 0 0)'
            code.append(f"tl.to({_js(wipe)},{{clipPath:{_js(clip)},duration:{_number(right-left)},ease:'none'}},{_number(left)});")
    exit_duration=animation["exit_duration"]
    exit_start=began+animation["clock_duration"]-exit_duration
    left,right=max(0.,exit_start),min(scene_duration,exit_start+exit_duration)
    if animation["exit"]!="none" and right>left:
        lo,hi=(left-exit_start)/exit_duration,(right-exit_start)/exit_duration
        code.append(f"tl.to({_js(alpha)},{{opacity:{_number(1-hi)},duration:{_number(right-left)},ease:'none'}},{_number(left)});")
        if animation["exit"]=="slide":
            eased=4*hi**3 if hi<.5 else 1-4*(1-hi)**3
            code.append(f"tl.to({_js(move)},{{y:{_number(32*eased*scale)},duration:{_number(right-left)},ease:{_text_ease('inout3',lo,hi)}}},{_number(left)});")
    if preset in ("typewriter","word_reveal"):
        mode="grapheme" if preset=="typewriter" else "word"
        count=layout["grapheme_count"] if mode=="grapheme" else layout["word_count"]
        if count:
            events={}
            for line_index,line in enumerate(layout["lines"]):
                if layout["style"]["letter_spacing"]!=0:
                    for unit in line["units"]:
                        index=unit["index"] if mode=="grapheme" else unit["word_index"]
                        if index<0:
                            continue
                        at=began+duration*(index+1)/count
                        if 0<at<=scene_duration:
                            selector=",".join(selectors[("unit",unit["index"])])
                            events[(at,selector)]={"opacity":1}
                else:
                    indices=sorted({unit["index"] if mode=="grapheme" else unit["word_index"] for unit in line["units"]})
                    for index in indices:
                        if index<0:
                            continue
                        at=began+duration*(index+1)/count
                        if 0<at<=scene_duration:
                            snapshot={"reveal_mode":mode,"reveal_fraction":(index+1)/count}
                            selector=",".join(selectors[("line",line_index)])
                            events[(at,selector)]={"textContent":typography.line_prefix(line,snapshot,layout)}
            # Initial values are part of the timeline so reverse/out-of-order
            # seeking restores the exact clipped-clock state.
            for (kind,index),selection in selectors.items():
                selector=",".join(selection)
                if kind=="line":
                    initial={"textContent":typography.line_prefix(layout["lines"][index],state,layout)}
                else:
                    unit=next(u for line in layout["lines"] for u in line["units"] if u["index"]==index)
                    limit=count if state["reveal_fraction"]>=1 else math.floor(count*state["reveal_fraction"]+1e-10)
                    initial={"opacity":1 if (unit["index"]<limit if mode=="grapheme" else unit["word_index"]<limit) else 0}
                code.append(f"tl.set({_js(selector)},{_js(initial)},0);")
            for (at,selector),properties in sorted(events.items()):
                code.append(f"tl.set({_js(selector)},{_js(properties)},{_number(at)});")
    return "\n".join(code)


def _copy_resource(root, directory, source, name):
    source, destination = _inside(root, source, True), _target(root, directory / name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise StudioError("La composición no reemplaza recursos existentes.", 409)
    shutil.copyfile(source, destination)
    return name


def _resource(root, directory, asset, staged):
    if asset["id"] in staged:
        return staged[asset["id"]]
    source = _inside(root, asset["local"], True)
    if source.stat().st_size + 512 * 1024 ** 2 > shutil.disk_usage(directory).free:
        raise StudioError("No hay espacio local suficiente para preparar el recurso sin agotar el disco.")
    digest = _sha(source)
    suffix = source.suffix.lower()
    name = "media/" + digest + suffix
    destination = _target(root, directory / name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if suffix in {".tif", ".tiff", ".bmp"}:
        name = "media/" + digest + ".png"
        destination = _target(root, directory / name)
        if not destination.exists():
            with Image.open(source) as image:
                image.convert("RGBA").save(destination)
    elif not destination.exists():
        shutil.copyfile(source, destination)
    if not destination.is_file():
        raise StudioError("No se pudo preparar el medio local.")
    staged[asset["id"]] = {"url": name, "original_sha256": digest,
                           "staged_sha256": _sha(destination), "original_path": str(source.relative_to(root)),
                           "image": suffix in native._OVERLAY_IMAGES}
    return staged[asset["id"]]


def _media_markup(dom_id, resource, start, end, source_in, track):
    common = f'id="{dom_id}" class="clip" data-start="{_number(start)}" data-duration="{_number(end - start)}" data-track-index="{track}"'
    style = "position:absolute;inset:0;width:100%;height:100%;object-fit:contain;"
    if resource["image"]:
        return f'<img {common} src="{resource["url"]}" alt="" style="{style}">'
    return f'<video {common} src="{resource["url"]}" muted playsinline preload="auto" data-hf-media-start-basis="local" data-media-start="{_number(source_in)}" style="{style}"></video>'


def _caption_assets(project, cfg, scene, scene_index, directory, root):
    """Reuse the measured native glyph placement, without animated caption CSS."""
    chunks = native._captions(project)
    duration = scene["_planned_end"] - scene["start"]
    intervals = []
    if scene.get("subtitle"):
        intervals.append((max(scene["start"], cfg["hook_seconds"]), scene["end"], str(scene["subtitle"])))
    else:
        intervals.extend((max(a, scene["start"]), min(b, scene["end"]), text) for a, b, text in chunks)
    markup = []
    for index, (start, end, text) in enumerate(intervals):
        if end <= start or text == scene.get("title"):
            continue
        frame = Image.new("RGBA", (cfg["width"], cfg["height"]))
        # Custom scenes have no presenter; the caption is an independent
        # timed top layer after the scene transform and resource overlays.
        native._decorate(frame, project, {**scene, "subtitle": text}, start, cfg, chunks)
        name = f"captions/scene_{scene_index}_{index}.png"
        path = _target(root, directory / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.save(path)
        markup.append(f'<img class="clip" id="caption_{scene_index}_{index}" src="{name}" alt="{html.escape(text, quote=True)}" data-start="{_number(start - scene["start"])}" data-duration="{_number(end-start)}" data-track-index="90" style="position:absolute;inset:0;width:100%;height:100%;z-index:90">')
    return markup


def build(project, root, directory, seconds=10, progress=None, cancel=None):
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        return _build(project,root,directory,seconds,progress,cancel)


def _build(project, root, directory, seconds=10, progress=None, cancel=None):
    """Create an editable, local HyperFrames project from the canonical schema.

    The destination must be new/empty. Non-custom scenes are faithfully
    rendered by the existing CPU engine and explicitly labelled as raster.
    Custom scenes contain the actual editable GSAP/DOM elements.
    """
    root = Path(root).resolve()
    directory = _target(root, directory)
    progress = progress or (lambda fraction, message: None)
    cfg = native._prepare(project, root, seconds)
    _font_identity(cfg, root)
    if directory.exists() and any(directory.iterdir()):
        raise StudioError("El proyecto HTML requiere una carpeta vacía; no se sobrescriben composiciones.", 409)
    directory.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < 512 * 1024 ** 2:
        raise StudioError("No hay espacio local suficiente para una composición segura.")
    source_sha = _sha(cfg["source"]["local"])
    visual_ids = set()
    for scene in cfg["scenes"]:
        if scene.get("asset_id"):
            visual_ids.add(scene["asset_id"])
        if scene.get("transition_asset_id"):
            visual_ids.add(scene["transition_asset_id"])
        visual_ids.update(layer["asset_id"] for layer in scene["overlays"])
        visual_ids.update(element["asset_id"] for element in scene.get("_design_media", []))
    if any(_sha(cfg["assets"][asset_id]["local"]) == source_sha for asset_id in visual_ids):
        raise StudioError("Una copia del crudo no puede ocultarse como recurso, motion, capa o transición.")
    staged_bytes = sum(cfg["assets"][asset_id]["local"].stat().st_size for asset_id in visual_ids)
    if staged_bytes > 4 * 1024 ** 3 or staged_bytes + 512 * 1024 ** 2 > shutil.disk_usage(directory).free:
        raise StudioError("Los recursos de la composición exceden el presupuesto seguro de disco local (4 GiB).")
    runtime, dependencies, status = _runtime(root)
    faces = []
    role_files = {}
    for key, filename in (("primary", "primary.ttf"), ("accent", "accent.ttf")):
        if cfg.get('branding'):
            path=_inside(root,cfg[key],True)
            filename=cfg['branding']['fonts'][key]['sha256'][:20]+path.suffix.lower()
        target=directory/'fonts'/filename
        if not target.exists():
            _copy_resource(root, directory, cfg[key], "fonts/" + filename)
        elif _sha(target)!=_sha(_inside(root,cfg[key],True)):
            raise StudioError('Identidad de fuente incompatible en la composición.',409)
        family = "AscendiaPrimary" if key == "primary" else "AscendiaAccent"
        kind='opentype' if filename.endswith('.otf') else 'truetype'
        faces.append(f"@font-face{{font-family:{family};src:url('fonts/{filename}') format('{kind}');font-display:block;font-weight:400;font-style:normal;}}")
        if cfg.get('branding'):
            face=cfg['branding']['fonts'][key]
            role_files[key]={'asset_id':face['asset_id'],'file':'fonts/'+filename,'sha256':face['sha256']}
    from .fonts import license_info
    selected_fonts, font_manifest = {}, []
    for order, (asset_id, asset) in enumerate(sorted(cfg.get("font_assets", {}).items())):
        metadata = typography.resolve_font({"font_asset_id": asset_id}, {}, cfg["font_assets"], root)
        path = _inside(root, metadata["path"], True)
        filename = metadata["sha256"][:20] + path.suffix.lower()
        family = "AscendiaFont" + str(order)
        selected_fonts[asset_id] = family
        if (directory/'fonts'/filename).exists():
            if _sha(directory/'fonts'/filename)!=metadata['sha256']:raise StudioError('La fuente del rol cambió durante empaquetado.',409)
        else:_copy_resource(root, directory, path, "fonts/" + filename)
        kind = "opentype" if path.suffix.lower() == ".otf" else "truetype"
        faces.append(f"@font-face{{font-family:{family};src:url('fonts/{filename}') format('{kind}');font-display:block;font-weight:400;font-style:normal;}}")
        license = license_info(asset, root)
        notice_name = None
        if license.get("status") in {"source_verified","bundled_notice_unverified"} and license.get("notice_path"):
            notice = _inside(root, license["notice_path"], True)
            if not notice.is_relative_to(_inside(root,"assets/fonts/licenses")) or not 1<=notice.stat().st_size<=65536:
                raise StudioError("El aviso de fuente no es un archivo permitido de assets/fonts/licenses.",403)
            if _sha(notice) != license.get("notice_sha256"):
                raise StudioError("El aviso de licencia de fuente cambió antes de empaquetar.", 409)
            notice_name = "fonts/license_" + license["notice_sha256"][:20] + ".txt"
            if (directory / notice_name).exists():
                if _sha(directory / notice_name) != license["notice_sha256"]:
                    raise StudioError("La composición contiene otro aviso de licencia; no se reemplaza.",409)
            else:
                _copy_resource(root, directory, notice, notice_name)
        font_manifest.append({"asset_id":asset_id,"file":"fonts/"+filename,"sha256":metadata["sha256"],"family":metadata["family"],"style":metadata["style"],
                              "synthetic_style":False,"license":{**license,"bundled_notice":notice_name}})
    if font_manifest:
        _json(directory / "fonts" / "font_manifest.json", {"fonts":font_manifest,"roles":role_files,"warning":"Actual fonts retain their face/license; no ASCENDIA approval is granted."})
    _copy_resource(root, directory, runtime / "gsap.min.js", "runtime/gsap.min.js")
    _copy_resource(root, directory, runtime / "MotionPathPlugin.min.js", "runtime/MotionPathPlugin.min.js")
    _copy_resource(root, directory, runtime / "third_party.json", "runtime/third_party.json")
    scenes = cfg["scenes"]
    raster_scenes = [scene for scene in scenes if scene.get("template") != "custom" or scene["type"] not in {"motion", "split"}]
    fallback = None
    if raster_scenes:
        progress(.02, "Preparación CPU de escenas existentes; motor declarado por escena")
        fallback = native.render(project, root, directory / "media/native_baseline.mp4", cfg["duration"],
                                 lambda fraction, message: progress(.02 + fraction * .18, message),
                                 lambda:_guard_cancel(root,directory,cancel))
    used = [{"asset_id": project["source"], "role": "narration", "start": 0., "end": cfg["duration"], "source_in": 0.}] if any(stream.get("codec_type")=="audio" for stream in cfg["source_info"]["streams"]) else []
    if fallback:
        for item in fallback["used_assets"]:
            if item["role"] in {"narration", "music", "sfx"}:
                continue
            if any(item["start"] >= s["start"] - 1e-6 and item["end"] <= s["end"] + 1e-6 for s in raster_scenes):
                used.append(item)
    (directory / "compositions").mkdir()
    staged, hosts, engines = {}, [], []
    for index, scene in enumerate(scenes):
        if _cancelled(cancel):
            raise StudioError("Adaptador cancelado.", 409)
        comp_id = f"scene_{index:03d}"
        w, h = cfg["width"], cfg["height"]
        duration = scene["_planned_end"] - scene["start"]
        visible_duration = scene["end"] - scene["start"]
        host = f'<div id="host_{comp_id}" class="clip" data-composition-id="{comp_id}" data-composition-src="compositions/{comp_id}.html" data-start="{_number(scene["start"])}" data-duration="{_number(visible_duration)}" data-width="{w}" data-height="{h}" data-track-index="{index}" style="position:absolute;inset:0;width:100%;height:100%"></div>'
        hosts.append(host)
        code = ["const tl=gsap.timeline({paused:true});"]
        markup = []
        if scene in raster_scenes:
            resource = {"url": "media/native_baseline.mp4", "image": False}
            markup.append(_media_markup("native_" + comp_id, resource, 0, visible_duration, scene["start"], 0))
            engines.append({"scene_id": scene.get("id"), "engine": "native CPU raster + HyperFrames container", "editable_dom_motion": False,
                            "template": scene.get("template"), "purpose": "Conserva la composición existente; no acredita animación GSAP del contenido raster."})
        else:
            design = scene["motion_design"]
            design_h = cfg['split_height'] if scene["type"] == "split" else h
            background = design.get("canvas", {}).get("background", "#101318")
            elements = sorted(design["elements"], key=lambda el: el.get("z", 0))
            for order, element in enumerate(elements):
                dom_id = f"el_{index}_{order}"
                inner_id = dom_id + "_inner"
                bw, bh = element.get("width", .25) * w, element.get("height", .25) * design_h
                start, end = element.get("start", 0), element.get("end", duration)
                if start >= visible_duration:
                    continue
                visible_end = min(end, visible_duration)
                style = f"position:absolute;left:0;top:0;width:{_number(bw)}px;height:{_number(bh)}px;transform-origin:50% 50%;z-index:{order};"
                inner_style = "position:absolute;inset:0;overflow:hidden;width:100%;height:100%;"
                if element["type"] == "text":
                    font_asset_id = element.get("font_asset_id")
                    family = selected_fonts[font_asset_id] if font_asset_id else "AscendiaPrimary" if element.get("font", "primary") == "primary" else "AscendiaAccent"
                    layout = typography.layout_element(element,(w,design_h),{"primary":cfg["primary"],"accent":cfg["accent"]},cfg.get("font_assets",{}),root)
                    content, text_selectors = _text_svg(layout,element,dom_id,family,duration)
                    code.append(_animate_text(element,layout,dom_id,text_selectors,duration))
                    if font_asset_id:
                        used.append({"asset_id":font_asset_id,"role":"font","element_id":element["id"],"scene_id":scene.get("id"),
                                     "start":scene["start"]+start,"end":scene["start"]+visible_end,"source_in":0.})
                elif element["type"] == "shape":
                    radius = "50%" if element.get("shape", "rect") == "ellipse" else _number(element.get("radius", 0) * w / 1080) + "px"
                    inner_style += f"background:{element.get('color','#ffffff')};border-radius:{radius};"
                    content = ""
                else:
                    resource = _resource(root, directory, cfg["assets"][element["asset_id"]], staged)
                    content = _media_markup(dom_id + "_media", resource, start, visible_end, element.get("source_in", 0), order + 1)
                    used.append({"asset_id": element["asset_id"], "role": "motion_element", "element_id": element["id"], "scene_id": scene.get("id"),
                                 "start": scene["start"] + start, "end": scene["start"] + visible_end, "source_in": element.get("source_in", 0)})
                timing = "" if element["type"] == "media" else f' class="clip" data-start="{_number(start)}" data-duration="{_number(visible_end-start)}" data-track-index="{order+1}"'
                markup.append(f'<div id="{dom_id}"{timing} style="{style}"><div id="{inner_id}" style="{inner_style}">{content}</div></div>')
                code.append(_animate_element("#" + dom_id, "#" + inner_id, element, duration, w, design_h))
            if scene["type"] == "split":
                upper = f'<div style="position:absolute;left:0;top:0;width:{w}px;height:{design_h}px;overflow:hidden;background:{background};">' + "".join(markup) + "</div>"
                camera = _split_camera(cfg, scene, root, directory, cancel)
                lower = f'<div style="position:absolute;left:0;top:{design_h}px;width:{w}px;height:{h-design_h}px;overflow:hidden;">' + _media_markup("camera_"+comp_id,camera,0,visible_duration,0,65) + "</div>"
                markup = [upper, lower]
                used.append({"asset_id":project["source"],"role":"split","start":scene["start"],"end":scene["end"],"source_in":scene.get("source_in",scene["start"]),
                             "region":"lower_authentic_cpu_crop","motion_height_px":cfg["split_height"],
                             "presenter_height_px":h-cfg["split_height"],"output_height_px":h})
            effects = scene.get("effects", {})
            # CSS/SVG are explicitly identified; contrast uses a midpoint,
            # unlike Pillow's image-dependent mean. Review remains required.
            brightness = native._number(effects.get("brightness", 0), "brightness", -1, 1)
            contrast = native._number(effects.get("contrast", 1), "contrast", 0, 3)
            saturation = native._number(effects.get("saturation", 1), "saturation", 0, 3)
            filter_id = comp_id + "_filter"
            filter_markup = f'<svg width="0" height="0" aria-hidden="true"><filter id="{filter_id}" color-interpolation-filters="sRGB"><feComponentTransfer><feFuncR type="linear" slope="1" intercept="{_number(brightness)}"/><feFuncG type="linear" slope="1" intercept="{_number(brightness)}"/><feFuncB type="linear" slope="1" intercept="{_number(brightness)}"/></feComponentTransfer><feComponentTransfer><feFuncR type="linear" slope="{_number(contrast)}" intercept="{_number((1-contrast)/2)}"/><feFuncG type="linear" slope="{_number(contrast)}" intercept="{_number((1-contrast)/2)}"/><feFuncB type="linear" slope="{_number(contrast)}" intercept="{_number((1-contrast)/2)}"/></feComponentTransfer><feColorMatrix type="saturate" values="{_number(saturation)}"/></filter></svg>'
            content = f'<div id="base_{comp_id}" style="position:absolute;inset:0;background:{background};filter:url(#{filter_id});transform-origin:50% 50%;">' + "".join(markup) + "</div>"
            markup = [filter_markup, content]
            scene_keys = []
            for frame in scene.get("keyframes", []):
                scene_keys.append({**frame, "x": frame.get("x", 0), "y": frame.get("y", 0), "ease": "linear"})
            scene_element = {"x": 0, "y": 0, "width": 1, "height": 1, "keyframes": scene_keys}
            code.append(_animate_element("#base_" + comp_id, "#base_" + comp_id, scene_element, duration, w, h, legacy=True))
            for order, layer in enumerate(scene["overlays"]):
                if layer["start"] >= visible_duration:
                    continue
                end = min(layer["end"], visible_duration)
                dom_id = f"overlay_{index}_{order}"
                resource = _resource(root, directory, cfg["assets"][layer["asset_id"]], staged)
                style = f"position:absolute;left:0;top:0;width:{_number(layer['width']*w)}px;height:{_number(layer['height']*h)}px;transform-origin:50% 50%;z-index:{70+order};mix-blend-mode:{layer['blend']};"
                markup.append(f'<div id="{dom_id}" style="{style}">' + _media_markup(dom_id + "_media", resource, layer["start"], end, layer["source_in"], 70+order) + "</div>")
                keys = [{**frame, "time": frame["time"] + layer["start"], "x": layer["x"] + frame.get("x", 0), "y": layer["y"] + frame.get("y", 0), "opacity": layer["opacity"] * frame.get("opacity", 1)} for frame in layer.get("keyframes", [])]
                code.append(_animate_element("#" + dom_id, "#" + dom_id, {**layer, "keyframes": keys}, duration, w, h, legacy=True))
                used.append({"asset_id": layer["asset_id"], "role": "overlay", "layer_id": layer["id"], "scene_id": scene.get("id"), "start": scene["start"]+layer["start"], "end":scene["start"]+end,"source_in":layer["source_in"],"blend":layer["blend"],"opacity":layer["opacity"]})
            markup.extend(_caption_assets(project, cfg, scene, index, directory, root))
            if scene.get("transition_asset_id"):
                transition_start = max(0, duration - scene.get("transition_duration", .5))
                if transition_start < visible_duration:
                    resource = _resource(root, directory, cfg["assets"][scene["transition_asset_id"]], staged)
                    dom_id = "burn_" + comp_id
                    markup.append('<div style="position:absolute;inset:0;z-index:100;mix-blend-mode:screen;">' + _media_markup(dom_id, resource, transition_start, visible_duration, scene.get("transition_source_in", 0), 100) + "</div>")
                    used.append({"asset_id":scene["transition_asset_id"],"role":"transition","blend":"screen","start":scene["start"]+transition_start,"end":scene["end"],"source_in":scene.get("transition_source_in",0)})
            engines.append({"scene_id": scene.get("id"), "engine": "HyperFrames + GSAP DOM upper / native CPU original camera lower" if scene["type"] == "split" else "HyperFrames + GSAP DOM", "editable_dom_motion": True,
                            "template": "custom", "design_sha256": hashlib.sha256(_js(design).encode()).hexdigest(),
                            "effects": "SVG sRGB brightness offset / midpoint contrast / saturation; review required"})
        code.extend([f"tl.to({{}},{{duration:{_number(duration)}}},0);", f"window.__timelines[{_js(comp_id)}]=tl;"])
        composition = '<!doctype html><html><head><meta charset="UTF-8"></head><body><template><style>' + f'#{comp_id}_root' + '{position:absolute;inset:0;width:100%;height:100%;overflow:hidden;isolation:isolate;}</style>'
        composition += f'<div id="{comp_id}_root" data-composition-id="{comp_id}" data-width="{w}" data-height="{h}" data-duration="{_number(duration)}">' + "".join(markup) + '</div><script>{\n' + "\n".join(code) + '\n}</script></template></body></html>'
        (directory / "compositions" / (comp_id + ".html")).write_text(composition, encoding="utf-8")
    main = f'''<!doctype html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width={cfg['width']},height={cfg['height']}"><title>ASCENDIA · proyecto técnico editable</title><script src="runtime/gsap.min.js"></script><script src="runtime/MotionPathPlugin.min.js"></script><style>{''.join(faces)}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#101318;}}#main_root{{position:relative;width:100%;height:100%;overflow:hidden;}}.clip{{position:absolute;}}</style></head><body><div id="main_root" data-composition-id="main" data-start="0" data-width="{cfg['width']}" data-height="{cfg['height']}" data-fps="{_number(cfg['fps'])}" data-duration="{_number(cfg['duration'])}">{''.join(hosts)}</div><script>gsap.registerPlugin(MotionPathPlugin);window.__timelines=window.__timelines||{{}};{{const tl=gsap.timeline({{paused:true}});tl.to({{}},{{duration:{_number(cfg['duration'])}}},0);window.__timelines.main=tl;}}</script></body></html>'''
    (directory / "index.html").write_text(main, encoding="utf-8")
    _json(directory / "hyperframes.json", {"media":{"autoProxy":True}})
    def editable(path):
        relative = path.relative_to(directory)
        if not path.is_file() or len(relative.parts) > 2:
            return False
        if len(relative.parts) == 1:
            return path.name in {"index.html","hyperframes.json"}
        if relative.parts[0] == "media":
            return path.name == "native_baseline.mp4" or bool(re.fullmatch(r"[0-9a-f]{64}\.[a-z0-9]+",path.name))
        return relative.parts[0] in {"fonts","runtime","captions","compositions"}
    files = [{"path": str(path.relative_to(root)), "sha256": _sha(path)} for path in sorted(directory.rglob("*")) if editable(path)]
    manifest = {"directory":str(directory.relative_to(root)),"index":str((directory/"index.html").relative_to(root)),"duration":cfg["duration"],"width":cfg["width"],"height":cfg["height"],"fps":cfg["fps"],"scene_engines":engines,"used_assets":used,"staged_assets":staged,"files":files,"editable_files":[item["path"] for item in files],"editorial_approved":False,"adapter":status,"project_sha256":hashlib.sha256(_js(project).encode()).hexdigest()}
    _json(directory / "build.json", manifest)
    return manifest


def verify_receipt(receipt, root=ROOT):
    """Check actual files and current executable bytes, never trust a badge."""
    try:
        adapter = receipt["technical"]["hyperframes"]
        status = _installation(root)
        if not status["available"] or not status.get("module_current") or not adapter.get("verified_execution") or adapter.get("hardware_gpu") is not False:
            return False
        for key in ("adapter_sha256", "runtime_sha256", "cli_version", "cli_loader_sha256", "cli_bundle_sha256", "cli_code_sha256", "path_plugin_sha256", "pixel_code_sha256", "executable_fingerprints", "text_layout_runtime"):
            if adapter.get(key) != status.get(key):
                return False
        if _sha(_inside(root, receipt["path"], True)) != receipt["sha256"]:
            return False
        for entry in adapter["proof_files"]:
            if _sha(_inside(root, entry["path"], True)) != entry["sha256"]:
                return False
        checked = json.loads(_inside(root, adapter["check_path"], True).read_text())
        if not checked.get("ok") or checked.get("browserSkipped") is not False:
            return False
        return True
    except (KeyError, TypeError, ValueError, OSError, StudioError):
        return False


def _manual_fingerprints():
    from . import core
    if core.WORKSPACE_MODE:
        return core.manual_fingerprints()
    return {name: _sha(MANUAL_ROOT / name) for name in ("AGENTS.md", "PROMPT_MAESTRO.md", "INSTRUCCIONES.md", "STYLE_YO.md") if (MANUAL_ROOT / name).is_file()}


def _unchanged(initial,current):
    for key in ("pixel_code_sha256","cli_code_sha256","runtime_sha256","path_plugin_sha256","executable_fingerprints","text_layout_runtime"):
        if initial.get(key) != current.get(key):
            raise StudioError("El motor o sus dependencias cambiaron durante la prueba; genera evidencia nueva con el código actual.",409)


def snapshot_design(project, scene_id, root, output, progress=None, cancel=None):
    """Capture the base editable design in the real browser, without animation.

    This technical PNG does not approve the design or authorise animation.
    Original media and fonts are kept; all keyframes/paths and timing-only
    entrances are removed from the ephemeral composition.
    """
    root = Path(root).resolve()
    initial = _installation(root)
    output = _target(root, output)
    if output.suffix.lower() != ".png":
        raise StudioError("La captura del diseño debe tener extensión PNG.")
    selected = next((item for item in project.get("timeline", []) if item.get("id") == scene_id), None)
    if not selected or selected.get("type") not in {'motion','split'} or selected.get("template") != "custom":
        raise StudioError("La captura requiere una escena motion/custom o split/custom existente.")
    # Validate the original rather than silently repairing untrusted fields.
    cfg = native._prepare(project, root, min(10., float(selected["end"])))
    from .design import validate_design
    validate_design(selected, (cfg["width"],cfg["height"]))
    _font_identity(cfg, root)
    _output_guard(root,output,cfg)
    static = copy.deepcopy(project)
    scene = copy.deepcopy(selected)
    fps = cfg["fps"]
    duration = math.ceil(max(.05, 1 / fps) * fps - 1e-9) / fps
    if scene['type']=='split':
        state=native._camera_state(scene,0)
        for key in ('focus_x','focus_y','chin_y'):
            if key in state:scene[key]=state[key]
        scene['source_in']=scene.get('source_in',scene['start'])
        scene.pop('camera_anchors',None)
    scene.update(start=0., end=duration, keyframes=[], overlays=[])
    for key in ("transition_asset_id", "transition_duration", "transition_source_in", "subtitle"):
        scene.pop(key, None)
    for element in scene["motion_design"]["elements"]:
        element.pop("keyframes", None)
        element.pop("path", None)
        element.pop("text_animation", None)
        element.update(start=0., end=duration)
    static["timeline"] = [scene]
    static["transcript"] = {"words": [], "segments": []}
    static["audio"] = []
    progress = progress or (lambda fraction, message: None)
    with _execution_lock(root, cancel):
        directory = _target(root, ".estado/hyperframes/designs/" + uuid.uuid4().hex)
        manifest = build(static, root, directory, duration, progress, cancel)
        progress(.4, "Comprobación del diseño estático en navegador real")
        command = _cli(root, directory, ["check", str(directory), "--json", "--samples", "1", "--at", "0", "--no-browser-gpu", "--timeout", "30000"], "check", cancel, timeout=180)
        checked = _payload(command["stdout"])
        _json(directory / "check.json", checked)
        if not checked.get("ok") or checked.get("browserSkipped") is not False:
            raise StudioError("El navegador rechazó el diseño estático.")
        progress(.7, "Captura PNG del diseño base, sin keyframes ni trayectorias")
        capture = _cli(root, directory, ["snapshot", str(directory), "--at", "0", "--no-end", "--no-browser-gpu", "--describe", "false", "--timeout", "30000"], "snapshot", cancel, timeout=180)
        execution = _execution_proof(root,directory,[command,capture],False,cancel)
        files = sorted((directory / "snapshots").glob("*.png"))
        if len(files) != 1:
            raise StudioError("El navegador no devolvió una única captura estática.")
        with Image.open(files[0]) as image:
            if image.size != (cfg["width"], cfg["height"]):
                raise StudioError("La captura no coincide con el lienzo del diseño.")
        if _cancelled(cancel):
            raise StudioError("Captura cancelada.", 409)
        status = _installation(root)
        _unchanged(initial,status)
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = output.with_name(output.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            shutil.copyfile(files[0], staging)
            os.replace(staging, output)
        finally:
            staging.unlink(missing_ok=True)
        paths = [directory / "check.json", directory / "build.json", files[0],root/execution["path"],
                 *(root/path for path in execution["trace_paths"]), *(_inside(root, item["path"], True) for item in manifest["files"])]
        adapter = {**status, "verified_execution": True, "static_only": True,
                   "check_path": str((directory / "check.json").relative_to(root)), "build_path": str((directory / "build.json").relative_to(root)),
                   "proof_files": [{"path": str(p.relative_to(root)), "sha256": _sha(p)} for p in dict.fromkeys(paths)],
                   "editable_files": manifest["editable_files"], "commands": [{k:v for k,v in item.items() if k not in {"stdout","stderr"}} for item in (command,capture)],
                   "runtime_versions":execution["versions"],"execution_path":execution["path"],
                   "production_conformant": False}
        result = {"path": str(output.relative_to(root)), "size": output.stat().st_size, "sha256": _sha(output),
                  "width": cfg["width"], "height": cfg["height"], "scene_id": scene_id,
                  "technical": {"engine": "HyperFrames + GSAP", "static": True, "editorial_approved": False,
                                "human_review_required": True, "manual_fingerprints": _manual_fingerprints(),
                                "hyperframes": adapter}}
        _json(output.with_suffix(".json"), result)
        progress(1, "PNG técnico capturado; aprobación explícita del diseño pendiente")
        return result


def render(project, root, output, seconds=10, progress=None, cancel=None):
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        return _render(project,root,output,seconds,progress,cancel)


def _render(project, root, output, seconds=10, progress=None, cancel=None):
    """Execute real local browser checks and CPU MP4 capture, then mix voice."""
    root = Path(root).resolve()
    initial = _installation(root)
    output = _target(root, output)
    if output.suffix.lower() != ".mp4":
        raise StudioError("El adaptador exporta MP4.")
    cfg = native._prepare(project, root, seconds)
    _output_guard(root,output,cfg)
    progress = progress or (lambda fraction,message:None)
    begin = time.monotonic()
    with _execution_lock(root, cancel):
        directory = _target(root, ".estado/hyperframes/runs/"+uuid.uuid4().hex)
        directory.mkdir(parents=True,exist_ok=False)
        manifest = build(project, root, directory, seconds, progress, cancel)
        commands = []
        progress(.25,"Comprobación real del navegador local, sin GPU")
        command = _cli(root,directory,["check",str(directory),"--json","--samples","5","--at-transitions","--max-transition-samples","40","--snapshots","--no-browser-gpu","--timeout","30000"],"check",cancel,lambda:progress(.27,"HyperFrames: verificando HTML y escenas en navegador"),180)
        checked = _payload(command["stdout"])
        _json(directory/"check.json",checked)
        if not checked.get("ok") or checked.get("browserSkipped") is not False:
            raise StudioError("La comprobación real HyperFrames no pasó; no se exporta el candidato.")
        commands.append({k:v for k,v in command.items() if k not in {"stdout","stderr"}})
        progress(.4,"Inspección real de keyframes registrados")
        command = _cli(root,directory,["keyframes",str(directory),"--json"],"keyframes",cancel,timeout=120)
        _json(directory/"keyframes.json",_payload(command["stdout"]))
        commands.append({k:v for k,v in command.items() if k not in {"stdout","stderr"}})
        times = sorted({0., round(cfg["duration"]*.3,6),round(cfg["duration"]*.7,6),max(0.,cfg["duration"]-1/cfg["fps"])})
        command = _cli(root,directory,["snapshot",str(directory),"--at",",".join(_number(t) for t in times),"--no-end","--no-browser-gpu","--describe","false","--timeout","30000"],"snapshot",cancel,timeout=180)
        commands.append({k:v for k,v in command.items() if k not in {"stdout","stderr"}})
        snapshots = [p for p in sorted((directory/"snapshots").glob("*.png")) if p.is_file()]
        if len(snapshots)<len(times):
            raise StudioError("La captura del navegador no produjo las muestras solicitadas.")
        visual,candidate=directory/"visual.mp4",directory/"candidate.mp4"
        progress(.5,"Captura HyperFrames: un worker, CPU, dos hilos máximo")
        crf = int(native._number(project.get("settings",{}).get("crf",18),"CRF",0,51))
        command = _cli(root,directory,["render",str(directory),"--output",str(visual),"--fps",_number(cfg["fps"]),"--workers","1","--no-browser-gpu","--sdr","--quality","looks","--crf",str(crf),"--low-memory-mode","--experimental-fast-capture=false","--frames-cache-dir",str(_target(root,".estado/hyperframes/frame-cache")),"--browser-timeout","60"],"render",cancel,lambda:progress(.57,"Capturando fotogramas reales en navegador; CPU limitada"),min(86400,max(600,cfg["duration"]*45)))
        commands.append({k:v for k,v in command.items() if k not in {"stdout","stderr"}})
        progress(.75,"Mezcla de narración original continua, música y efectos")
        execution = _execution_proof(root,directory,commands,True,cancel)
        has_voice,audio_used=native._audio(project,cfg,visual,candidate,root,lambda:_guard_cancel(root,directory,cancel))
        info=native.probe_media(candidate,root)
        video = next((stream for stream in info["streams"] if stream.get("codec_type") == "video" and not stream.get("disposition",{}).get("attached_pic")), {})
        if (video.get("width"),video.get("height"))!=(cfg["width"],cfg["height"]) or abs(info["duration"]-cfg["duration"])>max(.15,2/cfg["fps"]):
            raise StudioError("Las dimensiones o duración reales del MP4 no coinciden.")
        progress(.85,"Auditoría técnica completa de vídeo y niveles de audio")
        technical=native.audit(candidate,root,[{"id":s.get("id"),"start":s["start"],"end":s["end"],"type":s["type"]} for s in cfg["scenes"]],lambda:_guard_cancel(root,directory,cancel))
        if _cancelled(cancel):
            raise StudioError("Adaptador cancelado.",409)
        status=_installation(root)
        _unchanged(initial,status)
        proof_paths=[directory/"check.json",directory/"keyframes.json",directory/"build.json",root/execution["path"],
                     *(root/path for path in execution["trace_paths"]),*snapshots]
        proof_paths.extend(_inside(root,item["path"],True) for item in manifest["files"])
        proof=[{"path":str(path.relative_to(root)),"sha256":_sha(path)} for path in dict.fromkeys(proof_paths)]
        technical.update(original_voice_present=has_voice,original_audio_present=has_voice,gpu_used=False,max_ffmpeg_threads=2,
                         audio_listened=False,editorial_approved=False,human_review_required=True,
                         font_primary=str(Path(cfg["primary"]).relative_to(root)),font_accent=str(Path(cfg["accent"]).relative_to(root)),
                         scene_engines=manifest["scene_engines"],overlay_count=sum(item["role"]=="overlay" for item in manifest["used_assets"]))
        technical["manual_fingerprints"] = _manual_fingerprints()
        animated = any(s.get("template")=="custom" and any(e.get("keyframes") or e.get("path") or
                       e.get("text_animation",{}).get("preset","none")!="none" or e.get("text_animation",{}).get("exit","none")!="none"
                       for e in s.get("motion_design",{}).get("elements",[])) for s in cfg["scenes"])
        dynamic_verified = animated and len({_sha(p) for p in snapshots}) >= 2 and technical["consecutive_frames_decoded"] >= 2
        technical["hyperframes"]={**status,"verified_execution":True,"tested_duration":info["duration"],"dynamic_motion_verified":dynamic_verified,"runtime_versions":execution["versions"],"execution_path":execution["path"],"check_path":str((directory/"check.json").relative_to(root)),"keyframes_path":str((directory/"keyframes.json").relative_to(root)),"build_path":str((directory/"build.json").relative_to(root)),"proof_files":proof,"commands":commands,"browser_snapshots":[str(p.relative_to(root)) for p in snapshots],"editable_files":manifest["editable_files"],"path_interpolation":"GSAP linear segments weighted by canvas-pixel distance","mask_animation":"GSAP clipPath of validated circle/inset data","elapsed_seconds":round(time.monotonic()-begin,3),"production_conformant":False}
        output.parent.mkdir(parents=True,exist_ok=True)
        os.replace(candidate,output)
        result={"path":str(output.relative_to(root)),"size":output.stat().st_size,"sha256":_sha(output),"md5":native._hash(output,"md5"),"duration":info["duration"],"width":cfg["width"],"height":cfg["height"],"fps":cfg["fps"],"used_assets":[*manifest["used_assets"],*audio_used],"technical":technical}
        _json(output.with_suffix(".json"),result)
        if dynamic_verified:
            _json(_target(root, ".estado/hyperframes/integration.json"), result)
        progress(1,"Candidato técnico HyperFrames exportado; revisión humana pendiente")
        return result
