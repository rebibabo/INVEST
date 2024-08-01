from CFG import *
from DDG import Identifier

class CG(AST):
    func_properties: Dict[str, Union[str, int, List[Dict[str, Union[str, int]]]]] = {}
    call_edge: Dict[str, List[str]] = {}
    return_edge: Dict[str, List[str]] = {}
    cg: Graph = Graph(directed=True)

    def __init__(self, cfg: CFG_GRAPH):
        self.cfg = cfg

    @timer
    def construct_cg(self):
        edges = []
        name_to_id = {name: str(node.id) for name, node in self.cfg.functions.items()}
        for funcname, func_node in self.cfg.functions.items():
            func_type = text(func_node).split(funcname)[0].strip()
            line = func_node.start_point[0] + 1
            func_id = str(func_node.id)
            param_nodes = self.query(func_node, types='parameter_declaration', nest=False)
            parameters, return_node_ids, call_sites = [], [], []
            for node in param_nodes:
                identifier_nodes = self.cfg.query(node, types='identifier', nest=False)
                if identifier_nodes:
                    param = text(identifier_nodes[0])
                    type = text(node).split(param)[0].strip()
                    parameters.append({'type': type, 'param': param, 'param_id': str(node.id)})
            print(f'constructing CG for {funcname:>40}', end='\r')
            call_site_nodes = self.query(func_node, types='call_expression', nest=True)
            for node in call_site_nodes:
                callee_name = text(node.child_by_field_name('function'))
                if callee_name not in self.cfg.functions:
                    continue
                edges.append((func_id, name_to_id[callee_name]))
                arguments = []
                for child in node.child_by_field_name('arguments').children[1:-1]:
                    if child.type != ',':
                        ids = list(Identifier(child).ids)
                        arguments.append(ids)
                call_sites.append({'callee_name': callee_name, 'arguments': arguments, 'call_site_id': str(node.id), 'callee_code': text(node), 'callee_line': node.start_point[0] + 1})
            return_nodes = self.query(func_node, types='return_statement', nest=True)
            for return_node in return_nodes:
                var = text(return_node).replace('return', '').replace(';', '').strip()
                return_node_ids.append({'return_node_id': str(return_node.id), 'return_var': var, 'return_line': return_node.start_point[0] + 1})
            func_properties = {'type': func_type, 'func_name': funcname, 'line': line, 'func_id': func_id, 'parameters': parameters, 'return_node_ids': return_node_ids, 'call_sites': call_sites}
            self.func_properties[funcname] = func_properties
            self.cg.add_vertex(func_id, **func_properties)
        # input(self.call_edge)
        # input(self.return_edge)
        self.cg.add_edges(edges)    # 一次性添加所有边比一个一个添加边要快得多
        print(f'{"finish constructing C G":-^70}')
 
    def see_graph(self, 
        pdf: bool = True, 
        view: bool = True
    ) -> None:
        self.construct_cg()
        dot = Digraph(strict=True)
        for node in self.cg.vs:
            # label = f'name: {node["func_name"]}\\nline: {node["line"]}\\ntype: {node["type"]}\\nparameters: {node["parameters"]}'
            parameters = ' | '.join([f'{param["type"]} {param["param"]}' for param in node["parameters"]])
            label = f'name: {node["func_name"]}\\nline: {node["line"]}\\ntype: {node["type"]}\\nparameters: {parameters}'
            if node.indegree() or node.outdegree():
                dot.node(node['func_id'], label=label, fontname='fangsong', shape='rectangle')
        for edge in self.cg.es:
            dot.edge(self.cg.vs[edge.source]['func_id'], self.cg.vs[edge.target]['func_id'])
        if pdf:
            dot.render('pdf/cg', view=view, cleanup=True, format='pdf')
            dot.clear()

    def __str__(self):
        str = ''
        for funcname in self.func_properties:
            str += '\n' + '='*100 + '\n'
            str += f'funcname:   {funcname}\n'
            str += f'type:       {self.func_properties[funcname]["type"]}\n'
            str += f'line:       {self.func_properties[funcname]["line"]}\nparameter:  | '
            for param in self.func_properties[funcname]["parameters"]:
                str += f'{param["type"]} {param["param"]} | '
            str += '\ncall_sites\n'
            for call_site in self.func_properties[funcname]["call_sites"]:
                str += f'   {call_site["callee_line"]:>5}: {call_site["callee_code"]}\n'
            str += 'return:     |'
            for return_node_id in self.func_properties[funcname]["return_node_ids"]:
                str += f'line: {return_node_id["return_line"]}   var: {return_node_id["return_var"]} | '
        return str

if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    cfg = CFG('c', code)
    cg = CG(cfg)
    cg.see_graph()
    cg.construct_cg()
    # print(cg)
