# import openai
import subprocess
import json
from openai import OpenAI
import re
import os
import xml
import ast
import xml.etree.ElementTree as ET
import textwrap
import inspect


client = OpenAI(
    api_key = "API_KEY",
)

def extract_functions(func_code):    
    # 함수 패턴 찾기 (docstring 포함 여부 고려)
    function_pattern = re.findall(r'(def\s+\w+\(.*?\):\s*(?:\"\"\"(.*?)\"\"\"\s*)?(.*?))(?=\ndef|\Z)', func_code, re.DOTALL)
    
    results = []
    for full_function, docstring, function_body in function_pattern:
        docstring = docstring.strip() if docstring else ""
        cleaned_function = re.sub(r'\"\"\".*?\"\"\"\s*', '', full_function, count=1, flags=re.DOTALL)
        # 주석 제거 ("#" 이후부터 줄 끝까지 제거)
        cleaned_function = re.sub(r'\s*#.*', '', cleaned_function)
        results.append((docstring, cleaned_function.strip()))
        print(f"docstring: {docstring}")
        print(f"code: {cleaned_function}")
    
    return results

def read_prompts_from_jsonl(file_path):
    prompts = []
    entry_points = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                try:
                    json_obj = json.loads(line.strip())
                    if 'prompt' in json_obj:
                        prompts.append(json_obj['prompt'])
                    if 'entry_point' in json_obj:
                        entry_points.append(json_obj['entry_point'])
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON line: {line}\nError: {e}")
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return prompts, entry_points


def extract_between(text, start, end):
    try:
        # 정규식을 사용하여 시작 문자열과 끝 문자열 사이의 내용을 추출
        pattern = re.escape(start) + r'(.*?)' + re.escape(end)
        matches = re.findall(pattern, text, re.DOTALL)  # DOTALL로 줄바꿈 포함 매칭
        return matches
    except Exception as e:
        print(f"Error: {e}")
        return []



def generate_code(description):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an assistant that writes python code."},
                {"role": "user", "content": f"Please complete python code just send it for the following task: {description}. To make it easier for users to understand, please specify the type of input parameters. For example: 'a: list[int]' or 'b: str', etc. Also, if there is a return value, please make sure to save that value in a variable named 'result' and then return that 'result' value."}
            ],
            temperature=0
        )
        
        # 생성된 코드 추출
        generated_code = response.choices[0].message.content.strip()
        return generated_code
    
    except Exception as e:
        return {"error": str(e)}
    
def get_source_segment(source_lines, node):
    """AST 노드로부터 원래 코드 조각 추출"""
    if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
        return "\n".join(source_lines[node.lineno - 1: node.end_lineno])
    return ""

def extract_body_code(func_node, source_lines):
    """함수 본문 전체 코드를 들여쓰기 맞춰 추출"""
    body_lines = [get_source_segment(source_lines, stmt) for stmt in func_node.body]
    return textwrap.dedent("\n".join(body_lines)).strip()

def extract_return_var(func_node):
    """마지막 return 문의 변수명을 추출"""
    for stmt in reversed(func_node.body):
        if isinstance(stmt, ast.Return):
            if isinstance(stmt.value, ast.Name):
                return stmt.value.id, stmt.lineno
    return None, None


def parse_function_signature(code: str):
    """주어진 파이썬 코드에서 함수 이름, 인자, 반환 여부를 추출"""
    tree = ast.parse(code)
    func_def = next((node for node in tree.body if isinstance(node, ast.FunctionDef)), None)
    if not func_def:
        raise ValueError("No function definition found.")

    func_name = func_def.name
    args = [arg.arg for arg in func_def.args.args]
    returns = ast.unparse(func_def.returns) if func_def.returns else "None"
    has_return = returns != "None"

    return {
        "name": func_name,
        "args": args,
        "has_return": has_return
    }

def create_function_block_xml(code):
    tree = ast.parse(code)
    source_lines = code.splitlines()
    function_defs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    blocks = []

    for func in function_defs:
        block = ET.Element("block")
        block.set("type", "ast_Summerized_FunctionDef")  # 여기 수정
        block.set("line_number", str(func.lineno))
        block.set("inline", "false")

        mutation = ET.SubElement(block, "mutation")
        mutation.set("decorators", str(len(func.decorator_list)))
        mutation.set("parameters", str(len(func.args.args)))
        mutation.set("returns", "true" if func.returns else "false")

        name_field = ET.SubElement(block, "field")
        name_field.set("name", "NAME")
        name_field.text = func.name

        for i, arg in enumerate(func.args.args):
            value = ET.SubElement(block, "value")
            value.set("name", f"PARAMETER{i}")

            param_block = ET.SubElement(value, "block")
            param_block.set("type", "ast_FunctionParameter")
            param_block.set("line_number", str(getattr(arg, "lineno", func.lineno)))
            param_block.set("movable", "false")
            param_block.set("deletable", "false")

            param_field = ET.SubElement(param_block, "field")
            param_field.set("name", "NAME")
            param_field.text = arg.arg

        # BODY block
        statement = ET.SubElement(block, "statement")
        statement.set("name", "BODY")

        has_return = any(isinstance(stmt, ast.Return) for stmt in func.body)
        body_block_type = "ast_ReturnFull" if has_return else "ast_Raw"
        body_block = ET.SubElement(statement, "block")
        body_block.set("type", body_block_type)
        body_block.set("line_number", str(func.body[0].lineno if func.body else func.lineno))

        body_field = ET.SubElement(body_block, "field")
        body_field.set("name", "TEXT")
        body_code = extract_body_code(func, source_lines)
        body_field.text = body_code

        if has_return:
            return_var, return_lineno = extract_return_var(func)
            if return_var:
                value = ET.SubElement(body_block, "value")
                value.set("name", "VALUE")

                return_block = ET.SubElement(value, "block")
                return_block.set("type", "ast_Name")
                return_block.set("line_number", str(return_lineno))

                var_field = ET.SubElement(return_block, "field")
                var_field.set("name", "VAR")
                var_field.text = return_var

        blocks.append(block)
        print(ET.tostring(block, encoding='unicode'))

    return blocks

def get_type_hint(arg: ast.arg) -> str:
    if arg.annotation:
        if isinstance(arg.annotation, ast.Name):
            return arg.annotation.id
        elif isinstance(arg.annotation, ast.Subscript):
            return arg.annotation.value.id  # e.g., List[int] -> List
    return "number"  # default fallback

def map_type_to_block(param_type: str) -> tuple[str, str, str]:
    """자료형에 따른 Blockly shadow block 매핑"""
    if param_type in ("int", "float", "number"):
        return "math_number", "NUM", "0"
    elif param_type == "str":
        return "text", "TEXT", ""
    elif param_type in ("list", "List"):
        return "lists_create_with", None, None  # no field
    elif param_type in ("dict", "Dict"):
        return None, None, None  # unsupported yet
    else:
        return "text", "TEXT", ""  # fallback

def has_explicit_return(func_def: ast.FunctionDef) -> bool:
    """함수 내부에 return 문이 존재하는지 검사"""
    class ReturnVisitor(ast.NodeVisitor):
        def __init__(self):
            self.found = False
        def visit_Return(self, node):
            if node.value is not None:
                self.found = True
    visitor = ReturnVisitor()
    visitor.visit(func_def)
    return visitor.found

def create_ast_call_block_from_code(code):
    tree = ast.parse(code)
    func_def = next((node for node in tree.body if isinstance(node, ast.FunctionDef)), None)
    if not func_def:
        raise ValueError("No function definition found.")

    func_name = func_def.name
    args = func_def.args.args

    block = ET.Element("block", type="procedures_callreturn")
    mutation = ET.SubElement(block, "mutation", name=func_name)

    for arg in args:
        ET.SubElement(mutation, "arg", name=arg.arg)

    for idx, arg in enumerate(args):
        param_type = get_type_hint(arg)
        shadow_type, field_name, field_value = map_type_to_block(param_type)

        value = ET.SubElement(block, "value", name=f"ARG{idx}")
        if shadow_type:
            shadow = ET.SubElement(value, "shadow", type=shadow_type)
            if field_name:
                field = ET.SubElement(shadow, "field", name=field_name)
                field.text = field_value
        else:
            # No shadow (e.g., for dict), leave input blank
            continue

    # XML 문자열 반환
    print(ET.tostring(block, encoding="unicode"))
    return block

def print_pretty_xml(elem):
    from xml.dom import minidom
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    print(reparsed.toprettyxml(indent="  "))

def save_code_to_file(code, file_path):
    try:
        # print(code)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(code)
        print(f"Code successfully saved to {file_path}")
        return True
    except Exception as e:
        print(f"Failed to save code to {file_path}. Error: {e}")
        return False

def generate_blockly_from_js_function(js_function_str):
    # 함수 이름과 파라미터 추출
    func_header_match = re.search(r'function\s+(\w+)\s*\((.*?)\)', js_function_str)
    if not func_header_match:
        raise ValueError("Function header not found")

    func_name = func_header_match.group(1)
    params = [param.strip() for param in func_header_match.group(2).split(',') if param.strip()]

    # Blockly 블록 정의
    block_def = {
        "type": func_name,
        "message0": func_name + " " + " ".join([f"%{i+1}" for i in range(len(params))]),
        "args0": [
            {
                "type": "input_value",
                "name": param.upper()
            } for param in params
        ],
        "output": None,
        "colour": 230,
        "tooltip": f"Custom block for {func_name}",
        "helpUrl": ""
    }

    # JavaScript 코드 생성기
    generator_code = f"""Blockly.JavaScript['{func_name}'] = function(block) {{
"""
    for param in params:
        generator_code += f"  var value_{param} = Blockly.JavaScript.valueToCode(block, '{param.upper()}', Blockly.JavaScript.ORDER_ATOMIC);\n"
    arg_list = ", ".join([f"value_{param}" for param in params])
    generator_code += f"  var code = '{func_name}(' + {arg_list} + ')';\n"
    generator_code += f"  return [code, Blockly.JavaScript.ORDER_FUNCTION_CALL];\n"
    generator_code += "};"

    # 결과 출력
    print("Blockly 블록 정의 (JSON):\n")
    print("Blockly.defineBlocksWithJsonArray([")
    print(json.dumps(block_def, indent=2))
    print("]);\n")

    print("Blockly JS Generator:\n")
    print(generator_code)

    return json.dumps(block_def, indent=2), generator_code

def generate_block_and_generator_code(func_code: str):
    print("Generated Code")
    print(func_code)
    tree = ast.parse(func_code)
    func = tree.body[0]  # 첫 번째 함수만 처리
    func_name = func.name
    args = func.args.args
    returns_value = isinstance(func.returns, ast.Name) and func.returns.id != "None"

    # Blockly block definition
    block_json = {
        "type": func_name,
        "message0": f"{func_name} " + " ".join([f"%{i+1}" for i in range(len(args))]),
        "args0": [],
        "output": "Boolean" if returns_value else None,
        "colour": 230,
        "tooltip": f"Generated block for {func_name}",
        "helpUrl": ""
    }

    for i, arg in enumerate(args):
        block_json["args0"].append({
            "type": "input_value",
            "name": arg.arg,
            "check": "Number"  # 기본값, 확장 가능
        })

    generator = f"Blockly.Python['{func_name}'] = function(block) {{\n"
    for arg in args:
        generator += f"  const {arg.arg} = Blockly.Python.valueToCode(block, '{arg.arg}', Blockly.Python.ORDER_ATOMIC);\n"
    arg_list = ", ".join([arg.arg for arg in args])
    generator += f"  const code = `{func_name}({arg_list})`;\n"
    
    if returns_value:
        generator += "  return [code, Blockly.Python.ORDER_FUNCTION_CALL];\n"
    else:
        generator += "  return [code + '\\n'];\n"
    
    generator += "};"

    # 결과 출력
    import json
    print("Blockly 블록 정의 (JSON):\n")
    print("Blockly.defineBlocksWithJsonArray([")
    print(json.dumps(block_json, indent=2))
    print("]);\n")

    print("Blockly Python Generator:\n")
    print(generator)


# 예제 사용
file_path = "data/human-eval-v2-20210705.jsonl"
prompts, entry_points = read_prompts_from_jsonl(file_path)
# solutions = read_solution_from_jsonl(file_path)


# 예시 자연어 설명
# prompt = "Return true if a given number is prime, and false otherwise.\n    >>> is_prime(6)\n    False\n    >>> is_prime(101)\n    True\n    >>> is_prime(11)\n    True\n    >>> is_prime(13441)\n    True\n    >>> is_prime(61)\n    True\n    >>> is_prime(4)\n    False\n    >>> is_prime(1)\n    False\n    \"\"\"\n"
prompt = "Return the summation of two input integers"
prompt = "Return sum of given integer list"
prompt = "Return the first capital letter of given string"

def generate_block_from_nld(prompt):
    output = generate_code(prompt)

    start_string = "```python"
    end_string = "```"

    output = generate_code(prompt)
    print(output)
    extracted_result = extract_between(output, start_string, end_string)

    print(extracted_result[0])

    # generate_blockly_from_js_function(extracted_result[0])
    xml_block = create_function_block_xml(extracted_result[0])

    #출력 예시: 
    """    
    <block type="ast_Summerized_FunctionDef" line_number="2" inline="false"><mutation decorators="0" parameters="1" returns="false" /><field name="NAME">is_prime</field><value name="PARAMETER0"><block type="ast_FunctionParameter" line_number="2" movable="false" deletable="false"><field name="NAME">n</field></block></value><statement name="BODY"><block type="ast_ReturnFull" line_number="3"><field name="TEXT">if n &lt;= 1:
        result = False
    elif n &lt;= 3:
        result = True
    elif n % 2 == 0 or n % 3 == 0:
        result = False
    else:
        i = 5
        while i * i &lt;= n:
            if n % i == 0 or n % (i + 2) == 0:
                result = False
                break
            i += 6
        else:
            result = True
    return result</field><value name="VALUE"><block type="ast_Name" line_number="18"><field name="VAR">result</field></block></value></block></statement></block>
    """

    call_block = create_ast_call_block_from_code(extracted_result[0])
    #출력 예시:
    """
    <block type="ast_Call" line_number="2" inline="true"><mutation arguments="1" returns="true" parameters="true" method="false" name="is_prime" message="is_prime" premessage="" colour="210" module=""><arg name="UNKNOWN_ARG:0" /></mutation><value name="ARG0"><block type="ast_Name" line_number="2"><field name="VAR">n</field></block></value></block>
    """

    print(xml_block)

generate_block_from_nld(prompt)

