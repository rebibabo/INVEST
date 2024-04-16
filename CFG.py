from AST import *
import html

def get_break_continue_node(node):
    # 找到node节点循环中的所有break和continue节点并返回
    break_nodes, continue_nodes = [], []
    for child in node.children:
        if child.type == 'break_statement':
            break_nodes.append(child)
        elif child.type == 'continue_statement':
            continue_nodes.append(child)
        elif child.type not in ['for_statement', 'while_statement', 'switch_statement']:    # 保证break和continue在当前循环里
            b_node, c_nodes = get_break_continue_node(child)
            break_nodes.extend(b_node)
            continue_nodes.extend(c_nodes)
    return break_nodes, continue_nodes

def get_edge(in_nodes):
    # 输入入节点，返回入边的列表，边为(parent_id, label)
    edge = []     
    for in_node in in_nodes:   
        parent, label = in_node
        parent_id = parent['id']
        edge.append((parent_id, label))
    return edge

class CFG(AST):
    def __init__(self, language, code):
        super().__init__(language, code)
        self.cfgs = {}  # 存放每一个函数的CFG图

    def properties(self, node):
        node_prop = super().properties(node)
        node_prop['is_branch'] = False
        if node.type == 'function_definition':
            node_prop['text'] = text(node.child_by_field_name('declarator').child_by_field_name('declarator'))  # 函数名
            node_prop['id'] = str(self.func_num)
        elif node.type in ['if_statement', 'while_statement', 'for_statement', 'switch_statement']:
            if node.type == 'if_statement':
                body = node.child_by_field_name('consequence')
            else:
                body = node.child_by_field_name('body')
            node_text = ''
            for child in node.children:
                if child == body:
                    break
                node_text += text(child)
            node_prop['text'] = node_text
            if node.type != 'switch_statement':
                node_prop['is_branch'] = True
        elif node.type == 'do_statement':
            node_prop['text'] = f'while{text(node.child_by_field_name("condition"))}'
            node_prop['is_branch'] = True
        elif node.type == 'case_statement':
            node_text = ''
            for child in node.children:
                if child.type == ':':
                    break
                node_text += ' ' + text(child)
            node_prop['text'] = node_text
            node_prop['is_branch'] = True
        elif node.type == 'labeled_statement':
            node_prop['text'] = text(node.child_by_field_name('label'))
        else:
            node_prop['text'] = text(node)
        return node_prop

    def create_cfg(self, node, in_nodes=[()]):
        # 输入当前节点，以及入节点，入节点为(node_info, edge_label)的列表，node_info['id']唯一确定一个节点，edge_label为边的标签
        if node.type == 'labeled_statement':  # 如果是label: statement语句
            CFG = []            
            edge = get_edge(in_nodes)
            node_info = self.properties(node)
            CFG.append((node_info, edge))   
            body = node.children[2]
            cfg, out_nodes = self.create_cfg(body, [(node_info, '')])   # 遍历label后的语句
            CFG.extend(cfg)
            return CFG, out_nodes
        if node.child_count == 0:   # 如果in_nodes为空，说明没有入节点，跳过
            return [], in_nodes
        if node.type == 'function_definition':      # 如果节点是函数，则创建函数节点，添加参数节点，并且递归遍历函数的compound_statement
            CFG = []
            body = node.child_by_field_name('body')
            func_node_info = self.properties(node)
            param_nodes = self.query(node, types='parameter_declaration', nest=False)
            last_node_info = func_node_info
            for param_node in param_nodes:
                param_node_info = self.properties(param_node)
                CFG.append((param_node_info, [(last_node_info['id'], '')]))
                last_node_info = param_node_info
            body_CFG, _ = self.create_cfg(body, [(last_node_info, '')])
            return body_CFG + CFG + [(func_node_info, [])], []
        elif node.type == 'compound_statement':     # 如果是复合语句，则递归遍历复合语句的每一条statement
            CFG = []
            for child in node.children:
                cfg, out_nodes = self.create_cfg(child, in_nodes)
                CFG.extend(cfg)
                in_nodes = out_nodes
            return CFG, in_nodes
        elif 'preproc' in node.type:    # preproc_if, preproc_ifdef, preproc_def, preproc_call
            CFG = []
            if node.type in ['preproc_if', 'preproc_ifdef']:
                for child in node.children[2:]:
                    cfg, out_nodes = self.create_cfg(child, in_nodes)
                    CFG.extend(cfg)
                    in_nodes = out_nodes
            return CFG, in_nodes
        elif node.type not in ['if_statement', 'while_statement', 'for_statement', 'switch_statement', 'case_statement', 'translation_unit', 'do_statement']:  # 如果是普通的语句
            edge = get_edge(in_nodes)
            node_info = self.properties(node)
            in_nodes = [(node_info, '')]
            if node.type in ['return_statement', 'break_statement', 'continue_statement']:  # return，break，continue为非条件跳转语句，不会到下一条语句
                return [(node_info, edge)], []
            elif node.type == 'goto_statement':  # goto语句将本句连接到对应label的节点上
                label = text(node.child_by_field_name('label'))
                if label in self.labeled_nodes:
                    return [(node_info, edge)] + [(self.labeled_nodes[label], [(str(node.id), '')])], []
                else:
                    return [(node_info, edge)], []
            else:
                return [(node_info, edge)], in_nodes
        elif node.type == 'if_statement':   # if语句
            CFG = []
            edge = get_edge(in_nodes)
            node_info = self.properties(node)
            CFG.append((node_info, edge))
            body = node.child_by_field_name('consequence')  # 获取if的主体部分
            cfg, out_nodes = self.create_cfg(body, [(node_info, 'True')])
            CFG.extend(cfg)
            alternate = node.child_by_field_name('alternative') # 获取else的主体部分，可能是else，也可能是else if
            if alternate:       # if else 或者 if else if
                body = alternate.children[1]
                cfg, al_out_nodes = self.create_cfg(body, [(node_info, 'False')])
                CFG.extend(cfg)
                return CFG, out_nodes + al_out_nodes
            else:               # 只有if
                return CFG, out_nodes + [(node_info, 'False')]
        elif node.type in ['for_statement', 'while_statement']:     # for和while循环
            CFG = []
            edge = get_edge(in_nodes)
            node_info = self.properties(node)
            CFG.append((node_info, edge))
            body = node.child_by_field_name('body')     # 获取循环主体
            cfg, out_nodes = self.create_cfg(body, [(node_info, 'True')])
            CFG.extend(cfg)
            for out_node in out_nodes:  # 将循环主体的出节点与循环的开始节点相连
                parent, label = out_node
                parent_id = parent['id']
                CFG.append((node_info, [(parent_id, label)]))
            break_nodes, continue_nodes = get_break_continue_node(node)     # 求得循环内的break和continue节点
            out_nodes = [(node_info, 'False')]      # 循环体的出节点开始节点，条件为False
            for break_node in break_nodes:      
                out_nodes.append((self.properties(break_node), ''))   # 将break节点添加到out_nodes中
            for continue_node in continue_nodes:
                CFG.append((node_info, [(str(continue_node.id), '')]))     # 将continue节点连接到循环的开始节点
            return CFG, out_nodes
        elif node.type == 'do_statement':   # do while循环
            CFG = []
            edge = get_edge(in_nodes)
            node_info = self.properties(node)
            body = node.child_by_field_name('body')     # 获取循环主体
            cfg, out_nodes = self.create_cfg(body, [])  # 注意到body的入节点为空，真实的入节点是while跳转过来的
            first_node = self.properties(body.children[1]) if body.child_count > 2 else node_info  # 循环主体的第一条语句
            CFG.append((first_node, edge))
            CFG.extend(cfg)
            edge = get_edge(out_nodes)
            CFG.append((node_info, edge))   #  将循环主体的出节点与条件节点相连
            CFG.append((first_node, [(node_info['id'], 'True')]))   # 将条件节点连接到循环主体的开始节点
            out_nodes = [(node_info, 'False')]      # 循环体的出节点开始节点，条件为False
            break_nodes, continue_nodes = get_break_continue_node(node)     # 求得循环内的break和continue节点
            for break_node in break_nodes:
                out_nodes.append((self.properties(break_node), ''))
            for continue_node in continue_nodes:
                CFG.append((node_info, [(str(continue_node.id), '')]))
            return CFG, out_nodes
        elif node.type == 'switch_statement':   # switch语句
            CFG = []
            all_out_nodes = []
            edge = get_edge(in_nodes)
            switch_node_info = self.properties(node)
            CFG.append((switch_node_info, edge))
            body = node.child_by_field_name('body')     # 获取switch的主体部分
            in_nodes = [(switch_node_info, '')]     # case的入节点
            for case_node in body.children[1:-1]:
                if case_node.children[0].type == 'case': # 如果为case
                    index = 3
                    case_name = text(case_node.child_by_field_name('value'))
                else:
                    index = 2
                    case_name = 'default'
                case_node_info = self.properties(case_node)
                for i in range(len(in_nodes)):  # case的入边来自switch语句和上一条语句的out_nodes
                    if in_nodes[i][0] == switch_node_info:
                        in_nodes[i] = (switch_node_info, case_name) # 如果in_node为switch到case的边，则把标签改为case_name
                edge = get_edge(in_nodes)   
                CFG.append((case_node_info, edge))
                in_nodes = [(case_node_info, '')]   # 现在case里面第一条语句的入节点为case节点
                out_nodes = []
                for child in case_node.children[index:]:
                    cfg, out_nodes = self.create_cfg(child, in_nodes)
                    CFG.extend(cfg)
                    in_nodes = out_nodes
                break_nodes, _ = get_break_continue_node(case_node)     # 获取所有的break节点
                if break_nodes: # 如果有break节点，则把break节点加到switch的all_out_nodes中
                    for break_node in break_nodes:
                        all_out_nodes.append((self.properties(break_node), ''))
                in_nodes = out_nodes + [(switch_node_info, '')] # 下一条case语句的入节点为当前case最后一条语句的out_nodes加上switch到case的边
            return CFG, all_out_nodes + out_nodes   # 最终返回switch语句所有的break节点和最后一条case的out_nodes

    def convert_cfg_to_graph(self, cfg):
        # 将CFG转换为iGraph，并加上exit节点
        graph = Graph(directed=True)
        node_ids = set()
        node_ids_with_out_edge = set()   # 有出边的节点
        condition_nodes = {}    # 保存条件节点, 如果条件语句只有一个分支，则将另一个分支指向exit节点
        for end, edges in cfg:
            if end['id'] not in node_ids:
                node_ids.add(end['id'])
                graph.add_vertex(end['id'], **end)
            for start, label in edges:
                node_ids_with_out_edge.add(start)
                if label in ['True', 'False']:
                    condition_nodes.setdefault(start, []).append(label)
        one_exit_condition_node = [node for node, labels in condition_nodes.items() if len(labels) == 1]
        last_node = list(node_ids - node_ids_with_out_edge) + one_exit_condition_node  # 没有出边的节点
        # 构造CFG的边
        for end, edges in cfg:
            for start, label in edges:
                if start in node_ids:
                    graph.add_edge(start, end['id'], label=label)
        # 删除死代码，即不是函数入口节点且入度为0的节点
        delete_nodes = graph.vs.select(lambda x: x['type'] != 'function_definition' and x.indegree() == 0)
        while len(delete_nodes) > 0:
            delete_ids = []
            for node in delete_nodes:
                delete_ids.append(node.index)
            graph.delete_vertices(delete_ids)
            delete_nodes = graph.vs.select(lambda x: x['type'] != 'function_definition' and x.indegree() == 0)
        # 添加exit节点，使得所有出度为0或者不完善的分支节点指向exit
        graph.add_vertex(f'-{self.func_num}', type='function_exit', text='exit', id=f'-{self.func_num}')
        for node_id in last_node:
            if node_id in one_exit_condition_node:
                graph.add_edge(node_id, f'-{self.func_num}', label='False')
            else:
                graph.add_edge(node_id, f'-{self.func_num}', label='')
        return graph

    @timer
    def construct_cfg(self):
        for i, (funcname, func_node) in enumerate(self.functions.items()):
            self.func_num = i
            print(f'constructing CDG for {funcname:>40}', end='\r')
            labeled_nodes = self.query(func_node, types='labeled_statement', nest=True)
            self.labeled_nodes = {text(node.child_by_field_name('label')): self.properties(node) for node in labeled_nodes}
            cfg, _ = self.create_cfg(func_node)
            self.cfgs[funcname] = self.convert_cfg_to_graph(cfg)
        print(f'{"finish constructing CFG":-^70}')

    def draw_graph(self, graph):
        dot = Digraph()
        for node in graph.vs:
            label = html.escape(node['text']) + '\\n' + f"{node['type']} | {node['line']}"
            if node['is_branch']:
                dot.node(node['id'], shape='diamond', label=label, fontname='fangsong')
            elif node['type'] == 'function_definition':
                dot.node(node['id'], label=label, fontname='fangsong')
            elif node['type'] == 'function_exit':
                dot.node(node['id'], label='exit', fontname='fangsong')
            else:
                dot.node(node['id'], shape='rectangle', label=label, fontname='fangsong')
        for edge in graph.es:
            next_node, label = edge.target, edge['label'] if 'label' in edge.attributes() else ''
            dot.edge(graph.vs[edge.source]['id'], graph.vs[next_node]['id'], label=label)
        return dot

    def see_graph(self, pdf=True, view=False):
        self.construct_cfg()
        for funcname, cfg in self.cfgs.items():
            dot = self.draw_graph(cfg)
            if pdf:
                dot.render('pdf/' + funcname, view=view, cleanup=True)
                dot.clear()
        return self.cfgs

if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    cfg = CFG('c', code)
    cfg.see_graph(view=True)
    cfg.construct_cfg()

'''
bprint_bytes没有exit
default_print_section_header没有分析def
writer_print_integer if也要有exit边
'''
