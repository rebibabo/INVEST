from CFG import *
# diff文件格式参考 https://www.ruanyifeng.com/blog/2012/08/how_to_read_diff.html

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

class DIFF(AST):
    def __init__(self, language, code, diff_path):
        self.language = language
        super().__init__(language, code)
        with open(diff_path, 'r', encoding='utf-8') as f:
            diff = f.read()
        old_lines, new_lines, func_names = self.preprocess(diff)
        for i, old_line in enumerate(old_lines):
            func_node = self.functions[func_names[i]]
            self.get_cruial_variable_lines(old_line, func_node)

    def preprocess(self, diff):
        diff_lines = diff.split('\n') 
        # 按照开头为@@切分不同的diff块
        diff_start_line = 4
        diff_blocks = []
        for i, line in enumerate(diff_lines[5:]):
            if line.startswith('@@'):
                diff_blocks.append(diff_lines[diff_start_line:i+5])
                diff_start_line = i+5
        diff_blocks.append(diff_lines[diff_start_line:])
        # 提取出每一个diff_block中old line和new line以及对应文件的行号
        old_lines, new_lines, func_names = [], [], []
        for block in diff_blocks:
            diff_info = block[0].split('@@')[1].strip()
            function = block[0].split('@@')[2]
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
            
    def get_cruial_variable_lines(self, lines, func_node):
        # 提取出某一行的关键变量，包含声明语句、赋值语句、函数调用语句和控制语句
        def helper(node):
            id_nodes = []
            if node.type == 'function_declarator':
                param_nodes = self.query(node, 'parameter_declaration')
                for param_node in param_nodes:
                    ids = Identifier(param_node)
                    for id in ids:
                        id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'declaration'})
                body_id_nodes = helper(node.parent.child_by_field_name('body'))
                id_nodes += body_id_nodes
            elif node.type == 'declaration':
                ids = Identifier(node)
                for id in ids:
                    id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'declaration'})
            elif node.type == 'expression_statement':
                node = node.children[0]
                if node.type == 'assignment_expression':
                    ids = Identifier(node)
                    for id in ids:
                        id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'assignment'})
                    right_node = node.child_by_field_name('right')  # 如果赋值语句右边是函数调用，则继续提取
                    if right_node.type == 'call_expression':
                        node = right_node
                if node.type == 'call_expression':
                    ids = Identifier(node)
                    for id in ids:
                        id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'call_expression'})                
            elif node.type in ['if_statement', 'while_statement', 'for_statement', 'do_statement']:
                condition = node.child_by_field_name('condition')
                ids = Identifier(condition)
                for id in ids:
                    id_nodes.append({'id':id, 'line':node.start_point[0] + 1, 'type':'control_statement'})
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
            if node['line'] in lines and node not in return_ids:    # 只获取和修改行一样的变量
                return_ids.append(node)
        print(return_ids)
        return return_ids
                    

if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    diff = DIFF('c', code, 'diff.txt')