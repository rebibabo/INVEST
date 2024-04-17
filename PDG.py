from CG import *
from CFG import *
from CDG import *
from DDG import *
from igraph import Graph
import pickle

class PDG(CFG):
    def __init__(self, language, code):
        super().__init__(language, code)
        self.construct_cfg()
        self.ddg = DDG(self)
        self.ddg.construct_ddg()
        self.cdg = CDG(self)
        self.cdg.construct_cdg()
        self.cg = CG(self)
        self.cg.construct_cg()
        self.pdgs = {} 
        self.ipdg = None 

    @timer
    def construct_pdg(self):
        for funcname, cfg in self.cfgs.items():
            print(f'constructing PDG for {funcname:>40}', end='\r')
            ddg, cdg = self.ddg.ddgs[funcname], self.cdg.cdgs[funcname]
            self.pdgs[funcname] = copy.deepcopy(cfg)
            self.pdgs[funcname].delete_edges(self.pdgs[funcname].get_edgelist())
            for ddg_edge in ddg.es:
                src, tgt, label = ddg_edge.source, ddg_edge.target, ddg_edge['label']
                self.pdgs[funcname].add_edge(src, tgt, label=label, type='DDG')
            for cdg_edge in cdg.es:
                src, tgt = cdg_edge.source, cdg_edge.target
                self.pdgs[funcname].add_edge(src, tgt, label='', type='CDG')
        print(f'{"finish constructing PDG":-^70}')

    def print_graph(self, graph):
        for node in graph.vs:
            print(node.index, node.attributes())
        for edge in graph.es:
            print(edge.index, graph.vs[edge.source]['name'], graph.vs[edge.target]['name'], edge.attributes())
        print('---------------------------------')
    
    @timer
    def interprocedual_analysis(self, save=False):  # 进行跨函数分析，加上了call边和return边，其中call边为第i个实参所使用的变量到第i个形参，return边为返回值到调用点
        print(f'{"constructing interprocedual PDG":-^70}')
        edges, e_properties = [], {'type':[], 'label':[]}
        ipdg = Graph(directed=True)
        pdgs = list(self.pdgs.values())
        ipdg = pdgs[0].union(pdgs[1:])
        for funcname, properties in self.cg.func_properties.items():
            call_sites = properties['call_sites']
            for call_site in call_sites:
                callee_name, arguments, line = call_site['callee_name'], call_site['arguments'], call_site['callee_line']
                callee_properties = self.cg.func_properties[callee_name]
                call_site_nodes = self.pdgs[funcname].vs.select(lambda x: x['line'] == line)
                if len(call_site_nodes) == 0:
                    continue
                call_site_id = call_site_nodes[0]['id']
                callee_parameters = callee_properties['parameters']
                for i, ids in enumerate(arguments):
                    for id in ids:
                        if i > len(callee_parameters) - 1:
                            print(call_site['callee_code'])
                            print(callee_name, callee_parameters, arguments, i, ids, line)
                        edges.append((call_site_id, callee_parameters[i]['param_id']))
                        e_properties['type'].append('CALL')
                        e_properties['label'].append(id)
                for return_node_id in callee_properties['return_node_ids']:
                    edges.append((return_node_id['return_node_id'], call_site_id))
                    e_properties['type'].append('RETURN')
                    e_properties['label'].append(return_node_id['return_var'])
        ipdg.add_edges(edges, e_properties)
        self.ipdg = ipdg

    def draw_graph(self, graph):
        dot = Digraph()
        for node in graph.vs:
            label = html.escape(node['text']) + '\\n' + f"{node['type']} | {node['line']}"
            if node['is_branch']:
                dot.node(node['id'], shape='diamond', label=label, fontname='fangsong')
            elif node['type'] == 'function_definition':
                dot.node(node['id'], label=label, fontname='fangsong')
            elif node['type'] == 'function_exit':
                continue
            else:
                dot.node(node['id'], shape='rectangle', label=label, fontname='fangsong')
        for edge in graph.es:
            next_node, label = edge.target, edge['label'] if 'label' in edge.attributes() else ''
            if edge['type'] == 'CDG':
                label = 'CDG'
            elif edge['type'] == 'DDG':
                label = 'DDG: ' + label
            elif edge['type'] == 'CALL':
                label = 'CALL: ' + label
            elif edge['type'] == 'RETURN':
                label = 'RETURN: ' + label
            dot.edge(graph.vs[edge.source]['id'], graph.vs[next_node]['id'], label=label)
        return dot

    def see_graph(self, pdf=True, view=False, save=False):
        if not self.ipdg:
            for funcname, pdg in self.pdgs.items():
                # print(funcname)
                dot = self.draw_graph(pdg)
                if pdf:
                    dot.render('pdf/' + funcname, view=view, cleanup=True)
        else:
            dot = self.draw_graph(self.ipdg)
            if pdf:
                dot.render('pdf/ipdg', view=view, cleanup=True)

if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    pdg = PDG('c', code)
    pdg.construct_pdg()
    pdg.interprocedual_analysis(save=False)
    pdg.see_graph(view=True)