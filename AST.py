from tree_sitter import Parser, Language, Node
from graphviz import Digraph
from igraph import Graph
import pickle
import os
import re
import time
from typing import Callable, Literal, Dict, List, Any, Tuple, Union
import tree_sitter

text = lambda node: node.text.decode('utf-8')
constant_type = ['number_literal', 'string_literal', 'character_literal', 'preproc_arg', 'true', 'false', 'null']   # 常量类型

def timer(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        start = time.time()
        res = func(*args, **kwargs)
        end = time.time()
        print(f'{func.__name__:<30} cost time: {end - start:.2f}s')
        return res
    return wrapper

def replace_from_code(
    operation: List[Tuple[int, Union[int, str]]], 
    code: str
) -> str:
    code = code.encode('utf-8')
    diff = 0        # 插入删除产生的长度差
    # 按照第一个元素，及修改的位置从小到大排序，如果有同一个位置删除和插入，先删除再插入
    operation = sorted(operation, key=lambda x: (x[0], 1 if type(x[1]) is int else 0, -len(x[1]) if type(x[1]) is not int else 0)) # 第一个key是index，第二个key是先做删除操作，第三个key是先插入字符串少的
    for op in operation:
        if type(op[1]) is int:  # 如果第二个元素是一个数字
            if op[1] < 0:      # 如果小于0，则从op[0]往左删除op[1]个元素
                del_num = op[1]
            else:       # 则从op[0]往左删除到op[1]个元素
                del_num = op[1] - op[0]
            code = code[:op[0] + diff + del_num] + code[op[0] + diff:]
            diff += del_num
        else:                   # 如果第二个元素是字符串，则从op[0]往右插入该字符串，diff+=len(op[1])
            code = code[:op[0] + diff] + op[1].encode('utf-8') + code[op[0] + diff:]
            diff += len(op[1])
    operation.clear()
    return code.decode('utf-8', errors='ignore')

def define_replace(
    body: str, 
    *params: List[str]
) -> Callable[[List[str]], str]:  # 宏替换，输入宏的定义和参数，返回一个函数，输入参数返回替换后的字符串
    if not len(*params):    # 简单的变量名替换
        def func(params: List[str]):
            return body
    else:   # 如果是带有参数的宏
        ori_body = body.replace('{', '{{').replace('}', '}}')   # 删除所有的{}，因为format函数会将{}替换成{0}，{1}...
        body = ori_body
        for i, param in enumerate(*params):
            not_sub_word = [word for word in body.split() if '##' in word]
            body = body.replace(f'##{param}', '{' + str(i) + '}').replace(f'{param}##', '{' + str(i) + '}')    # str##param -> strparam , param##str -> paramstr
            body = body.replace(f'#{param}', f'"{param}"').replace(f'#@{param}', f"'{param}'")  # #param -> "param" , #@param -> 'param'
            for subword in ori_body.split():    # param -> {i}
                if param in subword and subword not in not_sub_word:
                    new_subword = subword.replace(param, '{' + str(i) + '}')
                    body = body.replace(subword, new_subword)
        def func(params: List[str]):
            params = [param.strip() for param in params]
            return body.format(*params).replace('{{', '{').replace('}}', '}'.replace('""', ''))
    return func

def remove_comments_and_include(code: str) -> str:
    '''删除代码中的注释和#include'''
    code = re.sub(r'//.*?(\n|$)', '\n', code)   # 删除单行注释
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)  # 删除多行注释
    code = re.sub(r'#include.*?(\n|$)', '', code)  # 删除#include
    return code

class AST:
    functions: Dict[str, Node] = {}
    code: str
    language: Literal["c"]
    parser: tree_sitter.Parser
    root_node: Node
    func_num: int

    def __init__(self, 
        language: Literal['c'], 
        code: str
    ) -> None:
        self.language = language
        if not os.path.exists(f'./build/{language}-languages.so'):
            if not os.path.exists(f'./tree-sitter-{language}'):
                os.system(f'git clone https://github.com/tree-sitter/tree-sitter-{language}')
            Language.build_library(
                f'./build/{language}-languages.so',
                [
                    f'./tree-sitter-{language}',
                ]
            )
        LANGUAGE = Language(f'./build/{language}-languages.so', language)
        parser = Parser()
        parser.set_language(LANGUAGE)
        self.parser = parser
        # self.preprocess_code(code)
        self.code = code
        self.root_node = self.parser.parse(bytes(code, 'utf8')).root_node
        function_nodes = self.query(self.root_node, types='function_definition', nest=False)
        for node in function_nodes:
            funcnode = self.query(node, types='function_declarator', nest=False)[0]
            funcname = text(funcnode.child_by_field_name('declarator'))
            self.functions[funcname] = node
        self.func_num = len(self.functions)

    def preprocess_code(self, code: str) -> str:
        '''预处理代码，去掉注释，替换宏定义等'''
        operation: List[Tuple[int, Union[int, str]]] = []
        code = remove_comments_and_include(code)
        root_node = self.parser.parse(bytes(code, 'utf8')).root_node
        define_nodes = self.query(root_node, types=['preproc_def', 'preproc_function_def'], nest=False)
        # 宏定义的替换参考文章https://zhuanlan.zhihu.com/p/367761694
        defines: Dict[str, str] = {}
        define_line: Dict[str, int] = {}
        for node in define_nodes:
            name = text(node.child_by_field_name('name'))
            value = text(node.child_by_field_name('value'))
            params_node = self.query(node, types='identifier', nest=False)[1:]
            params = [text(p) for p in params_node]
            defines[name] = define_replace(value, params)
            define_line[name] = node.start_point[0]
        # 找出来所有的宏定义以后，遍历所有变量名节点，将宏定义替换成对应的字符串
        identifier_nodes = self.query(root_node, types='identifier', nest=False)
        for node in identifier_nodes:
            name = text(node)
            if name in defines and node.start_point[0] > define_line[name] and node.parent.type != 'call_expression':
                operation.append((node.end_byte, node.start_byte))
                operation.append((node.start_byte, defines[name]([])))
        code = replace_from_code(operation, code)
        operation.clear()
        root_node = self.parser.parse(bytes(code, 'utf8')).root_node
        # 遍历所有函数调用节点，将宏定义替换成对应的字符串
        call_nodes = self.query(root_node, types='call_expression', nest=True)
        for node in call_nodes:
            name = text(node.child_by_field_name('function'))
            arguments = text(node.child_by_field_name('arguments'))[1:-1].split(',')
            if name in defines and node.start_point[0] > define_line[name]:
                operation.append((node.end_byte, node.start_byte))
                operation.append((node.start_byte, defines[name](arguments)))
        self.code = replace_from_code(operation, code)
        self.root_node = self.parser.parse(bytes(self.code, 'utf8')).root_node
        with open('preprocess.c', 'w') as f:
            f.write(self.code)

    def properties(self, node: Node) -> Dict[str, Any]:
        return {'type': node.type, 'start_byte': node.start_byte, 'end_byte': node.end_byte, 'start_point': node.start_point, 'end_point': node.end_point, 'text': text(node), 'id': str(node.id), 'line': node.start_point[0] + 1}

    def query(self, 
        root_node: Node, 
        types: Union[Literal["all"], List[str]]='all', 
        nest: bool = True
    ) -> List[Node]:
        '''
        遍历根节点root_node
        如果types为all，则返回所有节点，否则返回指定类型的节点
        nest为False时，匹配到的第一个节点时就不往下遍历了，否则还要递归遍历所有子节点
        '''
        if not root_node:
            return []
        nodes: List[Node] = []
        if types != 'all' and not isinstance(types, list):
            types = [types]
        def help(node):
            if types == 'all' or node.type in types:
                nodes.append(node)
                if not nest:
                    return 
            for child in node.children:
                help(child)
        help(root_node)
        return nodes

    def build_tree(self, 
        save: bool = False, 
        filepath: str = ''
    ) -> None:
        '''输入代码code，返回AST树'''
        self.ast = Graph(directed=True)
        nodes = self.query(self.root_node, types='all', nest=True)
        for node in nodes:
            node_prop = self.properties(node)
            self.ast.add_vertex(node_prop['id'], **node_prop)
        for node in nodes:
            for child in node.children:
                self.ast.add_edge(str(node.id), str(child.id))
        if save:
            pickle.dump(self.ast, open(f'{filepath}.pkl', 'wb'))

    def see_graph(self, 
        filepath: str = 'pdf/ast', 
        pdf: bool = True, 
        view: bool = False, 
        save: bool = False
    ) -> None:
        '''
        生成AST树的可视化图
        filepath: 生成的文件名
        pdf: 是否生成pdf文件
        view: 是否打开pdf文件
        save: 是否保存生成的graphml文件
        '''
        self.build_tree(save=save, filepath=filepath)
        dot = Digraph(comment='AST Tree', strict=True)
        for node in self.ast.vs:
            dot.node(str(node.index), shape='rectangle', label=node['type'], fontname='fangsong')
            successor = self.ast.successors(node)
            if successor:
                for succ in self.ast.successors(node):
                    dot.edge(str(node.index), str(succ))
            else:
                dot.node(str(-node.index), shape='ellipse', label=node['text'], fontname='fangsong')
                dot.edge(str(node.index), str(-node.index))
        dot.format = 'pdf'
        if pdf:
            dot.render(filepath, view=view, cleanup=True)

    def tokenize(self) -> List[str]:
        '''输入代码code，返回token列表'''
        def tokenize_help(node, tokens):
            if not node.children:
                tokens.append(text(node))
                return
            for n in node.children:
                tokenize_help(n, tokens)
        tokens: List[str] = []
        tokenize_help(self.root_node, tokens)
        return tokens

    def check_syntax(self) -> bool:
        '''检查代码是否有语法错误'''
        error_nodes = self.query(self.root_node, types='ERROR', nest=True)
        for i, node in enumerate(error_nodes):
            print(f"error {i:<3} : line {node.start_point[0]:<3} row {node.start_point[1]:<3} ---- line {node.end_point[0]:<3} row {node.end_point[1]:<3}")
            print(f"error code: {text(node)}")
        return self.root_node.has_error

if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    ast = AST('c', code)
    ast.see_graph(view=True)
    # print(ast.tokenize())
    # ast.check_syntax()