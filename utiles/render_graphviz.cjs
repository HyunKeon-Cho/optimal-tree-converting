// Use the Graphviz WebAssembly bundled with Interactive Graphviz, without changing it.
const fs = require('fs');
const path = require('path');
const [rendererDir, dotPath, svgPath, symbolsDir] = process.argv.slice(2);
global.document = { currentScript: { src: path.join(rendererDir, 'hpccjswasm.js') } };
const { graphviz } = require(path.join(rendererDir, 'hpccjswasm.js'));
const files = ['and.svg', 'nand.svg', 'not.svg'].map(name => ({
    path: path.join(symbolsDir, name).replace(/\\/g, '/'),
    data: fs.readFileSync(path.join(symbolsDir, name), 'utf8'),
}));
graphviz.layout(fs.readFileSync(dotPath, 'utf8'), 'svg', 'dot', {
    wasmBinary: fs.readFileSync(path.join(rendererDir, 'graphvizlib.wasm')),
    files,
}).then(svg => fs.writeFileSync(svgPath, svg)).catch(error => {
    console.error(error);
    process.exitCode = 1;
});
