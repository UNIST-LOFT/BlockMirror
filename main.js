import Python from './lib/blockly/python_compressed.js';
import JavaScript from './lib/blockly/javascript_compressed.js';
import Blockly from './lib/blockly/blockly_compressed.js';
import Blocks from './lib/blockly/blocks_compressed.js';
import { loadSkulpt } from './skulpt-loader.js';


const Sk = await loadSkulpt();

console.log(Blockly.Blocks);

Blockly.defineBlocksWithJsonArray([
  {
    "type": "is_prime",
    "message0": "is_prime %1",
    "args0": [
      {
        "type": "input_value",
        "name": "N"
      }
    ],
    "output": null,
    "colour": 230,
    "tooltip": "Custom block for is_prime",
    "helpUrl": ""
  }
  ]);
  

// Blockly.JavaScript['my_custom_block'] = function(block) {
//   const valueA = Blockly.JavaScript.valueToCode(block, 'A', Blockly.JavaScript.ORDER_ATOMIC) || '0';
//   const valueB = Blockly.JavaScript.valueToCode(block, 'B', Blockly.JavaScript.ORDER_ATOMIC) || '0';
//   const code = `${valueA} + ${valueB}`;
//   return [code, Blockly.JavaScript.ORDER_ADDITION];
// };

const workspace = Blockly.inject('blocklyDiv', {
  toolbox: document.getElementById('toolbox')
});


Blockly.JavaScript['is_prime'] = function(block) {
  var value_n = Blockly.JavaScript.valueToCode(block, 'N', Blockly.JavaScript.ORDER_ATOMIC);
  var code = 'is_prime(' + value_n + ')';
  return [code, Blockly.JavaScript.ORDER_FUNCTION_CALL];
};


// is_prime 함수 정의
function is_prime(n) {
  n = parseInt(n);
  if (n < 2) return false;
  for (let i = 2; i <= Math.sqrt(n); i++) {
    if (n % i === 0) return false;
  }
  return true;
}

function runCode() {
  const code = Blockly.JavaScript.workspaceToCode(workspace);
  console.log("코드:\n" + code);
  try {
    const result = eval(code);
    console.log("결과:", result);
  } catch (err) {
    console.error("실행 중 에러:", err);
  }
}

window.runCode = runCode;