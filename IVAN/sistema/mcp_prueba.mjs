import fs from 'node:fs';
import path from 'node:path';
import {Client} from '../.estado/herramientas/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import {StdioClientTransport} from '../.estado/herramientas/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
const root=path.resolve(import.meta.dirname,'..');process.chdir(root);
const env={...process.env,TMPDIR:`/proc/${process.pid}/cwd/.estado/tmp`,XDG_CACHE_HOME:path.join(root,'.estado/cache'),XDG_CONFIG_HOME:path.join(root,'.estado/config'),NODE_OPTIONS:'--import '+path.join(root,'sistema/confinar.mjs')};
const pkg=JSON.parse(fs.readFileSync(path.join(root,'.estado/herramientas/node_modules/@playwright/mcp/package.json')));
const bin=typeof pkg.bin==='string'?pkg.bin:Object.values(pkg.bin)[0];
const transport=new StdioClientTransport({command:'node',args:[path.join(root,'.estado/herramientas/node_modules/@playwright/mcp',bin),'--headless','--isolated','--executable-path','/usr/bin/google-chrome','--output-dir',path.join(root,'.estado/tmp/mcp')],env,stderr:'pipe'});
const client=new Client({name:'IVAN-validacion',version:'1.0'});await client.connect(transport);
try{
 const list=await client.listTools();const names=list.tools.map(t=>t.name);
 const url=process.argv[2]||'https://example.com';
 const nav=await client.callTool({name:'browser_navigate',arguments:{url}});
 const shot=await client.callTool({name:'browser_take_screenshot',arguments:{filename:path.join(root,'.estado/tmp/mcp/fuente_oficial.png'),type:'png'}});
 const proof={herramienta:'Playwright MCP',version:pkg.version,estado:!nav.isError&&!shot.isError?'operativo':'fallido',cantidad_herramientas:names.length,navegacion:!nav.isError,captura:!shot.isError};
 proof.url=url;proof.fecha=new Date().toISOString();fs.writeFileSync('.estado/tmp/playwright_mcp_prueba.json',JSON.stringify(proof,null,2));console.log(JSON.stringify(proof));
 await client.callTool({name:'browser_close',arguments:{}});
}finally{await client.close();}
