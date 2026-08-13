"use strict";

const vm = require("node:vm");

let source = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", chunk => { source += chunk; });
process.stdin.on("end", () => {
  try {
    const request = JSON.parse(source);
    if (!request || typeof request.code !== "string" || typeof request.input !== "object") {
      throw new Error("invalid sandbox request");
    }
    const sandbox = Object.create(null);
    sandbox.input = JSON.parse(JSON.stringify(request.input));
    sandbox.output = null;
    sandbox.globalThis = sandbox;
    const context = vm.createContext(sandbox, {
      name: "courseware-physics-sandbox",
      codeGeneration: { strings: false, wasm: false },
    });
    const program = `${request.code}\n;output = globalThis.coursewareModel.sample(input);`;
    new vm.Script(program, { filename: "generated-model.js" }).runInContext(context, { timeout: 500 });
    process.stdout.write(JSON.stringify({ ok: true, output: sandbox.output }));
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: String(error && error.message || error) }));
    process.exitCode = 1;
  }
});
