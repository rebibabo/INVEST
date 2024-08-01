from CFG import *
from graphviz import Graph
import copy
from typing import Set

class Identifier:
    ids: Set[str] = set()             # 普通变量
    index_ids: Set[str] = set()       # 数组索引   定义和使用时，作为use
    def_ids: Set[str] = set()         # 定义变量   定义时，作为def，使用时，排除在外
    field_ids: Set[str] = set()       # 结构体变量 定义时，作为一整个变量保存，使用时，要有所有前置成员的信息
    array_ids: Set[str] = set()       # 数组变量   定义时，只保留数组的名字，使用时，所有维度都要有信息流

    def __init__(self, expression_node: Node):
        # 输入利于a->b.c的变量
        self.expression_node = expression_node
        self.traverse(expression_node)
        self.ids |= self.ids | self.field_ids | self.array_ids

    def traverse(self, 
        node: Node, 
        type: str = ''
    ) -> None:
        if not node:
            return
        if node.type == 'identifier' and node.parent.type != 'call_expression':
            if type == 'index':     # a[i]中的i
                self.index_ids.add(text(node))
            if node.parent.type == 'declaration' or type == 'def':  # 定义变量 int a=1中的a
                self.def_ids.add(text(node))
            elif type == 'field':   # a->b中的a
                self.field_ids.add(text(node))
            elif type == 'update':  # a++中的a
                self.ids.add(text(node))
                self.def_ids.add(text(node))
            else:   # 普通变量
                self.ids.add(text(node))
        elif node.type == 'declaration':    # int a, b=1;
            for child in node.children[1:-1]:
                if child.type != ',':
                    self.traverse(child, 'def')
        elif node.type == 'pointer_expression': # *p
            self.traverse(node.children[1], type)
        elif node.type == 'pointer_declarator': # int *p
            self.traverse(node.children[1], 'def')
        elif node.type == 'field_expression':   # a->b.c
            node_text = text(node).replace(' ', '')
            if type == 'def':
                self.def_ids.add(node_text)
                self.traverse(node.children[0], '')
            elif type == 'update':
                self.def_ids.add(node_text)
                self.ids.add(node_text)
            else:
                self.field_ids.add(node_text)
                self.traverse(node.children[0], 'field')
        elif node.type == 'subscript_expression':   # a[i][j]
            node_text = text(node).replace(' ', '')
            if type == 'def':
                self.def_ids.add(node_text)
            else:
                self.traverse(node.children[0], type)
                self.traverse(node.children[2], 'index')
                self.array_ids.add(node_text)
        elif node.type == 'array_declarator':   # int a[n];
            self.traverse(node.children[0], 'def')
            self.traverse(node.children[2], 'index')
        elif node.type == 'assignment_expression':  # a=b;/a+=b
            if text(node.children[1]) != '=':
                self.traverse(node.child_by_field_name('left'), 'update')
            else:
                self.traverse(node.child_by_field_name('left'), 'def')
            self.traverse(node.child_by_field_name('right'), type)
        elif node.type == 'update_expression':  # a++
            self.traverse(node.child_by_field_name('argument'), 'update')
        elif node.type == 'init_declarator':    # int a=1;
            self.traverse(node.child_by_field_name('declarator'), 'def')
            self.traverse(node.child_by_field_name('value'), '')
        elif node.type == 'call_expression':    # func(a, b)
            func_name = text(node.child_by_field_name('function'))
            if func_name == 'scanf':
                self.traverse(node.child_by_field_name('arguments'), 'def')
            else:
                self.traverse(node.child_by_field_name('arguments'), type)
        else:
            for child in node.children:
                self.traverse(child, type)

    def __str__(self):
        return 'ids: {}\nindex_ids: {}\ndef_ids: {}\nfield_ids: {}\narray_ids: {}\n'.format(list(self.ids), list(self.index_ids), list(self.def_ids), list(self.field_ids), list(self.array_ids))
        
STATE = Dict[str, Set[int]]

class DDG:
    dict: Set[Tuple[str, int, int]] = set() # def -> use

    def __init__(self, cfg: CFG_GRAPH):
        self.cfg = cfg
        self.ddgs = copy.deepcopy(self.cfg.cfgs)
        for ddg in self.ddgs.values():
            ddg.delete_edges(ddg.get_edgelist())

    def init_func_state(self, func_node: Node) -> STATE:
        param_nodes = self.cfg.query(func_node, types='parameter_declaration', nest=False)
        out_state = {}
        for param_node in param_nodes:
            in_state = out_state
            identifier_nodes = self.cfg.query(param_node, types='identifier', nest=False)
            if identifier_nodes:
                node_name = text(identifier_nodes[0])
                in_state[node_name] = set([param_node.start_point[0] + 1])
                out_state = in_state
        return out_state

    def create_ddg(self, node: Node, in_state: STATE) -> STATE:
        in_state = copy.deepcopy(in_state)
        if not node:
            return in_state
        if node.type == 'compound_statement':
            for child in node.children[1:-1]:
                out_state = self.create_ddg(child, in_state)
                in_state = out_state
        elif node.type == 'if_statement':   # if语句输出的状态需要合并True分支和False分支的状态，如果没有else，则False分支为if语句的in状态
            condition = node.child_by_field_name('condition')
            id = Identifier(condition)
            for id_node in id.ids:
                self.add_def_use_edge(in_state, id_node, node.start_point[0] + 1)
            body = node.child_by_field_name('consequence')  # 获取if的主体部分
            true_path_state = self.create_ddg(body, in_state)
            false_path_state = {}
            alternative = node.child_by_field_name('alternative')
            if alternative:
                body = alternative.children[1]
                false_path_state = self.create_ddg(body, in_state)
                in_state = self.merge_state(true_path_state, false_path_state)
            else:
                in_state = self.merge_state(true_path_state, in_state)
        elif node.type == 'while_statement':        # 对于所有循环语句的状态，需要合并循环体的两次状态，因为循环体可能会执行多次，后面定义的语句可能会影响前面使用的语句
            condition = node.child_by_field_name('condition')
            id = Identifier(condition)
            for id_node in id.ids:
                self.add_def_use_edge(in_state, id_node, node.start_point[0] + 1)
            body = node.child_by_field_name('body')
            loop_body_state_1 = self.create_ddg(body, in_state)
            loop_body_state_2 = self.create_ddg(body, loop_body_state_1)
            in_state = self.merge_state(in_state, loop_body_state_1, loop_body_state_2)
        elif node.type == 'do_statement':
            condition = node.child_by_field_name('condition')
            id = Identifier(condition)
            body = node.child_by_field_name('body')
            loop_body_state_1 = self.create_ddg(body, in_state)
            loop_body_state_2 = self.create_ddg(body, loop_body_state_1)
            in_state = self.merge_state(in_state, loop_body_state_1, loop_body_state_2)
            for id_node in id.ids:
                self.add_def_use_edge(in_state, id_node, node.start_point[0] + 1)
        elif node.type == 'for_statement':
            initializer = node.child_by_field_name('initializer')
            condition = node.child_by_field_name('condition')
            update = node.child_by_field_name('update')
            id = Identifier(initializer)
            for id_node in id.def_ids:
                in_state[id_node] = set([node.start_point[0] + 1])
            for id_node in id.ids:
                self.add_def_use_edge(in_state, id_node, node.start_point[0] + 1)
            id = Identifier(condition)
            for id_node in id.ids:
                self.add_def_use_edge(in_state, id_node, node.start_point[0] + 1)
            out_state = self.create_ddg(update, in_state)
            body = node.child_by_field_name('body')
            loop_body_state_1 = self.create_ddg(body, out_state)
            loop_body_state_2 = self.create_ddg(body, loop_body_state_1)
            in_state = self.merge_state(in_state, loop_body_state_1, loop_body_state_2)
        elif node.type == 'switch_statement':
            condition = text(node.child_by_field_name('condition'))
            body = node.child_by_field_name('body')
            int_state_copy = copy.deepcopy(in_state)
            states = []
            for case_node in body.children[1:-1]:
                index = 3 if case_node.children[0].type == 'case' else 2
                case_value  = case_node.child_by_field_name('value')
                if case_value:
                    id = Identifier(case_value)
                    for id_node in id.ids:
                        self.add_def_use_edge(in_state, id_node, node.start_point[0] + 1)
                for child in case_node.children[index:]:
                    in_state = self.create_ddg(child, in_state)
                    states.append(in_state)
            in_state = self.merge_state(int_state_copy, *states)
        else:
            Id = Identifier(node)
            # input(text(node))
            # input(Id)
            for id in Id.ids:
                self.add_def_use_edge(in_state, id, node.start_point[0] + 1)

            for def_id in Id.def_ids:
                self.add_def_use_edge(in_state, def_id, node.start_point[0] + 1)
                in_state[def_id] = set([node.start_point[0] + 1])   # 对于这一行定义的节点，要Kill掉前面所有的定义状态
        # input(text(node))
        # input(in_state)

        out_state = in_state
        return out_state

    def merge_state(self, in_state: STATE, *out_states: List[STATE]) -> STATE:   # 合并多个状态，取并集
        out_state = in_state
        for state in out_states:
            for key, value in state.items():
                if key in out_state:
                    out_state[key] = out_state[key].union(value)
                else:
                    out_state[key] = value
        return out_state

    def add_def_use_edge(self, 
        state: STATE, 
        varname: str, 
        cur_line: int
    ) -> None:   # 增加def到use的边
        if varname not in state:    
            return
        for line in state[varname]:
            self.dict.add((varname, line, cur_line))

    def convert_dict_to_ddg(self, graph: Graph) -> None:
        for varname, line1, line2 in self.dict:
            def_nodes = graph.vs.select(line=line1)
            use_nodes = graph.vs.select(line=line2)
            def_node, use_node = None, None
            for node in def_nodes:
                if varname in node['text']:
                    def_node = node
                    break
            for node in use_nodes:
                if varname in node['text']:
                    use_node = node
                    break
            if not def_node or not use_node:
                continue
            graph.add_edge(def_node.index, use_node.index, label=varname)
            graph.simplify(combine_edges='first')

    @timer
    def construct_ddg(self) -> None:
        for i, (funcname, func_node) in enumerate(self.cfg.functions.items()):
            self.cfg.func_num = i
            funcname = text(self.cfg.query(func_node, types='function_declarator', nest=False)[0].child_by_field_name('declarator'))
            print(f'constructing DDG for {funcname:>40}', end='\r')
            init_state = self.init_func_state(func_node)
            body = func_node.child_by_field_name('body')
            self.create_ddg(body, init_state)
            self.convert_dict_to_ddg(self.ddgs[funcname])
            # print(self.dict)
            self.dict.clear()
        print(f'{"finish constructing DDG":-^70}')

    def see_graph(self, 
        pdf: bool = True, 
        view: bool = True
    ) -> None:
        self.construct_ddg()
        for funcname, ddg in self.ddgs.items():
            print(funcname)
            dot = self.cfg.draw_graph(ddg)
            dot.format = 'pdf'
            if pdf:
                dot.render('pdf/' + funcname, view=view, cleanup=True)


if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    cfg = CFG('c', code)
    cfg.construct_cfg()
    ddg = DDG(cfg)
    ddg.construct_ddg()
    ddg.see_graph(view=True)
    code = '&h->pkt.nals[i]'
    tree_node = ddg.cfg.parser.parse(code.encode('utf-8')).root_node
    id = Identifier(tree_node)
    print(id)