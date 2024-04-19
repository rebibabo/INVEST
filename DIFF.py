from CFG import *
# diff文件格式参考 https://www.ruanyifeng.com/blog/2012/08/how_to_read_diff.html
from typing import Dict
import difflib
from collections import defaultdict

def Identifier(node):
    ids = set()
    def helper(node):
        if not node:
            return
        if node.type == 'identifier' and node.parent.type != 'call_expression':
            if not text(node).replace('_','').isupper():
                ids.add(text(node))
        elif node.type == 'declaration':
            for child in node.children[1:-1]:
                if child.type != ',':
                    helper(child)
        elif node.type == 'pointer_expression':
            helper(node.children[1])
        elif node.type == 'pointer_declarator':
            helper(node.children[1])
        elif node.type == 'field_expression':
            ids.add(text(node).replace(' ', ''))
        elif node.type == 'subscript_expression':
            ids.add(text(node).replace(' ', ''))
        elif node.type == 'array_declarator':
            helper(node.children[0])
            helper(node.children[2])
        elif node.type == 'assignment_expression':
            helper(node.child_by_field_name('left'))
        elif node.type == 'update_expression':
            helper(node.child_by_field_name('argument'))
        elif node.type == 'init_declarator':
            helper(node.child_by_field_name('declarator'))
        elif node.type == 'call_expression':
            helper(node.child_by_field_name('arguments'))
        else:
            for child in node.children:
                helper(child)
    helper(node)
    return ids

class CV():
    def __init__(self,var,line,type,change) -> None:
        self.var = var
        self.line = line
        self.type = type
        self.change = change
    
    def __eq__(self,other):
        if self.var == other.var and self.type == other.type:
            return True
        return False
    def __str__(self):
        return f'{self.var}'


class DIFF():
    def __init__(self, language, old_code, new_code, diff_path):
        self.language = language
        self.old_codes = old_code.split('\n')
        self.new_codes = new_code.split('\n')
        self.old_ast = AST(language, old_code)
        self.new_ast = AST(language, new_code)
        # 记录当前diff中的关键变量
        self.old_cv = defaultdict(list) # {line:[cv]}
        self.new_cv = defaultdict(list)
        with open(diff_path, 'r', encoding='utf-8') as f:
            diff_lines = f.readlines()
        old_lines, new_lines, func_names = self.preprocess(diff_lines)
        for i in range(0,len(func_names)):
            old_func = self.old_ast.functions[func_names[i]]
            new_func = self.new_ast.functions[func_names[i]]
            if old_lines[i]:
                old_cv_dict =  self.get_cruial_variable_lines(old_lines[i], old_func, "delete")
            if new_lines[i]:
                new_cv_dict = self.get_cruial_variable_lines(new_lines[i], new_func, "add")
            # 对关键变量匹配结果进行去重
            self.remove_duplicates(old_cv_dict,new_cv_dict)
            self.old_cv.update(old_cv_dict)
            self.new_cv.update(new_cv_dict)
        self.old_cv = {k:v for k,v in self.old_cv.items() if v != []}
        self.new_cv = {k:v for k,v in self.new_cv.items() if v != []}
    
    def __str__(self) -> str:
        old = ''
        for k,vs in self.old_cv.items():
            for v in vs:
                old += f'{k} : {v.var} \n'
        new = ''
        for k,vs in self.new_cv.items():
            for v in vs:
                new += f'{k} : {v.var} \n'        
        return f'cv in old_file: \n{old}===========\ncv in new_file: \n{new}'                         

    def preprocess(self, diff_lines):
        """获取diff文件中所有的加号行和减号行"""
        # 按照开头为@@切分不同的diff块
        diff_start_line = 4
        diff_blocks = []
        for i, line in enumerate(diff_lines[5:],start=5):
            if line.startswith('@@'):
                diff_blocks.append(diff_lines[diff_start_line:i])
                diff_start_line = i
        diff_blocks.append(diff_lines[diff_start_line:])
        # 提取出每一个diff_block中old line和new line以及对应文件的行号
        old_lines, new_lines, func_names = [], [], []
        for block in diff_blocks:
            diff_info = block[0].split('@@')[1].strip()
            function = block[0].split('@@')[2]
            #TODO 从diff hunk头中获取函数名（可能不准确）
            func_name = function.split('(')[0].split(' ')[-1].replace('*', '').replace(' ','') 
            func_names.append(func_name)
            old, new = diff_info.split(' ')
            old_start_line = int(old[1:].split(',')[0])
            new_start_line = int(new[1:].split(',')[0])
            old_offset, new_offset = 0, 0
            old_line, new_line = [], []
            for line in block[1:]:
                if line.startswith('+'):
                    new_line.append(new_start_line+new_offset)
                    new_offset += 1
                elif line.startswith('-'):
                    old_line.append(old_start_line+old_offset)
                    old_offset += 1
                else:
                    new_offset += 1
                    old_offset += 1
            old_lines.append(old_line)
            new_lines.append(new_line)
        return old_lines, new_lines, func_names
            
    def get_cruial_variable_lines(self, lines, func_node, change_type) ->Dict:
        # 提取出某一行的关键变量，包含声明语句、赋值语句、函数调用语句和控制语句
        if change_type =='delete':
            ast_node = self.old_ast
        else:
            ast_node = self.new_ast
        def helper(node):
            id_nodes = defaultdict(list)
            if node.type == 'function_declarator':
                param_nodes = ast_node.query(node, 'parameter_declaration')
                for param_node in param_nodes:
                    ids = Identifier(param_node)
                    for id in ids:
                        line  =node.start_point[0] + 1
                        id_nodes[line].append(CV(id,line,'declaration',change_type))
                body_id_nodes = helper(node.parent.child_by_field_name('body'))
                id_nodes.update(body_id_nodes)
            elif node.type == 'declaration':
                ids = Identifier(node)
                for id in ids:
                    line = node.start_point[0] + 1
                    id_nodes[line].append(CV(id,line,'declaration',change_type))
            elif node.type in ['expression_statement','assignment_expression']: 
                if node.type == 'expression_statement':
                    node = node.children[0]
                if node.type == 'assignment_expression':
                    ids = Identifier(node)
                    for id in ids:
                        line = node.start_point[0] + 1
                        id_nodes[line].append(CV(id,line,'assignment',change_type))
                    right_node = node.child_by_field_name('right')  # 如果赋值语句右边是函数调用，则继续提取
                    if right_node.type == 'call_expression':
                        node = right_node
                    elif right_node.type == 'assignment_expression': # 赋值语句存在嵌套的情况 a=b= 0xffff;
                        right_node_ids = helper(right_node)
                        id_nodes[line].extend(right_node_ids[line])
                if node.type == 'call_expression':
                    ids = Identifier(node)
                    for id in ids:
                        line = node.start_point[0] + 1
                        id_nodes[line].append(CV(id,line,'call_expression',change_type))               
            elif node.type in ['if_statement', 'while_statement', 'for_statement', 'do_statement']:
                condition = node.child_by_field_name('condition')
                ids = Identifier(condition)
                for id in ids:
                    line = node.start_point[0] + 1
                    id_nodes[line].append(CV(id,line,'control_statement',change_type))
                body = node.child_by_field_name('body') if node.type != 'if_statement' else node.child_by_field_name('consequence')
                if body:
                    body_id_nodes = helper(body)
                    id_nodes.update(body_id_nodes)
                alternative = node.child_by_field_name('alternative')
                if alternative:
                    alternative_id_nodes = helper(alternative)
                    id_nodes.update(alternative_id_nodes)
            else:
                for child in node.children:
                    child_id_nodes = helper(child)
                    id_nodes.update(child_id_nodes)
            return id_nodes
        id_nodes = helper(func_node)
        return_ids = {}
        for key, cv_list in id_nodes.items():
            # 只获取和修改行一样的变量, 如果关键变量中有err和ret等只是返回值记录变量，则删除
            if key in lines:
                for cv in cv_list:
                    return_ids.setdefault(key,[])
                    if cv not in return_ids.get(key) and cv.var not in ['err','error','ret']:    
                        return_ids[key].append(cv)
        # print(return_ids)
        return return_ids

    def remove_duplicates(self,old_cv_dict: Dict,new_cv_dict: Dict):
        # 如果当前hunk中关键变量同时在old和new中出现，并且类型一致，则删除new中对应的items
        def get_all_cv(cv_dict):
            all_cv = []
            for cv_list in cv_dict.values():
                for cv in cv_list:
                    all_cv.append(cv)
            return all_cv
        all_old_cv = get_all_cv(old_cv_dict)
        all_new_cv = get_all_cv(new_cv_dict)
        
        for old_cv in all_old_cv:
            for new_cv in all_new_cv:
                if old_cv == new_cv:
                    old_code = self.old_codes[old_cv.line-1]
                    new_code = self.new_codes[new_cv.line-1]
                    # 1. 如果代码完全一致，则删除该行对应的关键变量
                    if old_code == new_code:
                        old_cv_dict.setdefault(old_cv.line,[])
                        new_cv_dict.setdefault(new_cv.line,[])
                        old_cv_dict.pop(old_cv.line)
                        new_cv_dict.pop(new_cv.line)
                        break
                    else:
                        # 2. 如果代码相似度较高,则只保留有差异的cv
                        match_level = difflib.SequenceMatcher(None,old_code,new_code).quick_ratio()
                        if match_level > 0.6: 
                            old_line_cvs = old_cv_dict.get(old_cv.line)
                            new_line_cvs = new_cv_dict.get(new_cv.line)
                            for cv in old_line_cvs:
                                for cv2 in new_line_cvs:
                                    if cv == cv2:
                                        old_line_cvs.remove(cv)
                                        new_line_cvs.remove(cv2)
                                        break
                        else:
                            # 3. 上述都不满足，则删除new中的cv
                            new_cv_dict[new_cv.line].remove(new_cv)
                    break
     
if __name__ == '__main__':
    old_code = r'{}'.format(open('./data/CVE-2013-6376_recalculate-apic-map/CVE-2013-6376_CWE-189_recalculate-apic-map_1.c_OLD.c', 'r', encoding='utf-8').read())
    new_code = r'{}'.format(open('./data/CVE-2013-6376_recalculate-apic-map/CVE-2013-6376_CWE-189_recalculate-apic-map_1.c_NEW.c', 'r', encoding='utf-8').read())

    diff = DIFF('c', old_code,new_code, './data/CVE-2013-6376_recalculate-apic-map/CVE-2013-6376_CWE-189_recalculate-apic-map_1.c.diff')
    print(diff)