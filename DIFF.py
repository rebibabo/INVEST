from CFG import *
# diff文件格式参考 https://www.ruanyifeng.com/blog/2012/08/how_to_read_diff.html
from typing import List
import difflib

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


class DIFF():
    def __init__(self, language, old_code, new_code, diff_path):
        self.language = language
        self.old_ast = AST(language, old_code)
        self.new_ast = AST(language, new_code)
        # 记录当前diff中的关键变量
        self.old_cv = []
        self.new_cv = []
        with open(diff_path, 'r', encoding='utf-8') as f:
            diff_lines = f.readlines()
        old_lines, new_lines, func_names = self.preprocess(diff_lines)
        for i in range(0,len(func_names)):
            old_func = self.old_ast.functions[func_names[i]]
            new_func = self.new_ast.functions[func_names[i]]
            if old_lines[i]:
                old_cv_list =  self.get_cruial_variable_lines(old_lines[i], old_func, "delete")
            if new_lines[i]:
                new_cv_list = self.get_cruial_variable_lines(new_lines[i], new_func, "add")
            # 对关键变量匹配结果进行去重
            self.remove_duplicates(old_cv_list,new_cv_list)
            self.old_cv.extend(old_cv_list)
            self.new_cv.extend(new_cv_list)
    
    def __str__(self) -> str:
        return f'cv in old_file: {self.old_cv}\ncv in new_file: {self.new_cv}'                         

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
            func_name = function.split('(')[0].split(' ')[-1].replace('*', '').replace(' ','') #从diff hunk头中获取函数名（可能不准确）
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
            
    def get_cruial_variable_lines(self, lines, func_node, change_type):
        # 提取出某一行的关键变量，包含声明语句、赋值语句、函数调用语句和控制语句
        if change_type =='delete':
            ast_node = self.old_ast
        else:
            ast_node = self.new_ast
        def helper(node):
            id_nodes = []
            if node.type == 'function_declarator':
                param_nodes = ast_node.query(node, 'parameter_declaration')
                for param_node in param_nodes:
                    ids = Identifier(param_node)
                    for id in ids:
                        id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'declaration', 'change':change_type})
                body_id_nodes = helper(node.parent.child_by_field_name('body'))
                id_nodes += body_id_nodes
            elif node.type == 'declaration':
                ids = Identifier(node)
                for id in ids:
                    id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'declaration', 'change':change_type})
            elif node.type == 'expression_statement':
                node = node.children[0]
                if node.type == 'assignment_expression':
                    ids = Identifier(node)
                    for id in ids:
                        id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'assignment', 'change':change_type})
                    right_node = node.child_by_field_name('right')  # 如果赋值语句右边是函数调用，则继续提取
                    if right_node.type == 'call_expression':
                        node = right_node
                if node.type == 'call_expression':
                    ids = Identifier(node)
                    for id in ids:
                        id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'call_expression', 'change':change_type})                
            elif node.type in ['if_statement', 'while_statement', 'for_statement', 'do_statement']:
                condition = node.child_by_field_name('condition')
                ids = Identifier(condition)
                for id in ids:
                    id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'control_statement', 'change':change_type})
                body = node.child_by_field_name('body') if node.type != 'if_statement' else node.child_by_field_name('consequence')
                if body:
                    body_id_nodes = helper(body)
                    id_nodes += body_id_nodes
                alternative = node.child_by_field_name('alternative')
                if alternative:
                    alternative_id_nodes = helper(alternative)
                    id_nodes += alternative_id_nodes
            else:
                for child in node.children:
                    child_id_nodes = helper(child)
                    id_nodes += child_id_nodes
            return id_nodes
        id_nodes = helper(func_node)
        return_ids = []
        for node in id_nodes:
            # 只获取和修改行一样的变量, 如果关键变量中有err和ret等只是返回值记录变量，则删除
            if node['line'] in lines and node not in return_ids and node['id'] not in ['err','error','ret']:    
                return_ids.append(node)
        # print(return_ids)
        return return_ids

    def remove_duplicates(self,old_cv_list,new_cv_list):
        # 如果当前hunk中关键变量同时在old和new中出现，并且类型一致，则删除new中对应的items
        #TODO 如果还需要进一步去除漏洞无关变量，需要对应的源代码
        for old_cv in old_cv_list:
            for new_cv in new_cv_list:
                if old_cv['id']==new_cv['id'] and old_cv['type'] == new_cv['type']:
                    new_cv_list.remove(new_cv) 
                    break 
            
                                     

if __name__ == '__main__':
    old_code = r'{}'.format(open('./data/CVE-2013-4483_SYSCALL-DEFINE4/CVE-2013-4483_CWE-189_SYSCALL-DEFINE4_1.c_OLD.c', 'r', encoding='utf-8').read())
    new_code = r'{}'.format(open('./data/CVE-2013-4483_SYSCALL-DEFINE4/CVE-2013-4483_CWE-189_SYSCALL-DEFINE4_1.c_NEW.c', 'r', encoding='utf-8').read())

    diff = DIFF('c', old_code,new_code, './data/CVE-2013-4483_SYSCALL-DEFINE4/CVE-2013-4483_CWE-189_SYSCALL-DEFINE4_1.c.diff')
    print(diff)