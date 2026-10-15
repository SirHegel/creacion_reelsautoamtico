// HyperFrames usa os.homedir() para cachés y estado. Aislarlo sin alterar HOME.
import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';
import {syncBuiltinESMExports} from 'node:module';
const root=path.resolve(import.meta.dirname,'..');
const local=path.join(root,'.estado/hyperframes');
fs.mkdirSync(local,{recursive:true});
os.homedir=()=>local;
syncBuiltinESMExports();
process.env.HYPERFRAMES_NO_TELEMETRY='1';
process.env.HYPERFRAMES_NO_UPDATE_CHECK='1';
process.env.HYPERFRAMES_BROWSER_PATH='/usr/bin/google-chrome';
process.env.HYPERFRAMES_FONT_CACHE_DIR=path.join(root,'.estado/cache/fuentes');
process.env.XDG_CACHE_HOME=path.join(root,'.estado/cache');
process.env.XDG_CONFIG_HOME=path.join(root,'.estado/config');
// PRIME: dirigir Chrome a la NVIDIA cuando el equipo tenga también gráfica Intel.
process.env.__NV_PRIME_RENDER_OFFLOAD='1';
process.env.__GLX_VENDOR_LIBRARY_NAME='nvidia';
process.env.__VK_LAYER_NV_optimus='NVIDIA_only';
