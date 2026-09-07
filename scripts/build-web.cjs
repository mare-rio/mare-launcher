const fs=require('node:fs'),path=require('node:path'),{buildSync}=require('esbuild');
const root=path.resolve(__dirname,'..'),out=path.join(root,'.build/web');
fs.rmSync(out,{recursive:true,force:true});fs.mkdirSync(out,{recursive:true});fs.cpSync(path.join(root,'web'),out,{recursive:true});fs.rmSync(path.join(out,'entry.js'));
buildSync({entryPoints:[path.join(root,'web/entry.js')],bundle:true,minify:true,format:'iife',target:'chrome90',define:{'process.env.NODE_ENV':'"production"'},outfile:path.join(out,'vendor/mare.js'),legalComments:'eof'});
console.log('Built local web assets in .build/web');
