from numpy import pi
from PDG import *
import igraph

def sortedNodesByLoc(list_node):
    _list = []
    for node in list_node:
        _list.append((node['line'], node))
    _list.sort(key=lambda x: x[0])
    hash_id = set()
    list_ordered_nodes = []
    for _, node in _list:
        if node['id'] not in hash_id:
            hash_id.add(node['id'])
            list_ordered_nodes.append(node)
    return list_ordered_nodes

class SLICE(PDG):
    edges: Set = set()
    visit_id: Set[int] = set()
    result_nodes: List = []
    slice: Graph = Graph(directed=True)

    def __init__(self, language: str, code: str):
        self.pdg = PDG(language, code)
        self.pdg.construct_pdg()
        self.pdg.interprocedual_analysis()
        # self.pdg.ipdg = pickle.load(open('ipdg.pkl', 'rb'))
        # dot = self.draw_graph(self.pdg.ipdg)
        # dot.render('pdf/ipdg', view=True, cleanup=True, format='pdf')
        # self.pdg.ipdg = pickle.load(open('ipdg.pkl', 'rb'))

    def spread(self, 
        node: Node, 
        cross_time: int,    # 跨函数层数
        direction: Literal['forward', 'backward']   # 前向、后向
    ) -> None:
        if cross_time == 0:
            return
        self.visit_id.add(node['id'])
        if direction == 'backward':
            for edge in self.pdg.ipdg.es.select(_target=node['id']):
                predecessor = self.pdg.ipdg.vs[edge.source]
                properties = predecessor.attributes()
                del properties['name']
                if edge['type'] == 'RETURN':
                    cross_time -= 1
                elif edge['type'] == 'CALL':
                    continue
                self.slice.add_vertex(predecessor['id'], **properties)
                if edge not in self.edges:
                    self.edges.add(edge)
                    self.slice.add_edge(predecessor['id'], node['id'], **edge.attributes())
                # print(node['text'], node['line'], '\n<==\n' + properties['text'], properties['line'], '\n' + edge['type'], edge['label'], '\n')
                # input()
                if predecessor['id'] not in self.visit_id:
                    self.result_nodes.insert(0, predecessor)
                    self.visit_id.add(predecessor['id'])
                    self.spread(predecessor, cross_time, 'backward')
        elif direction == 'forward':
            for edge in self.pdg.ipdg.es.select(_source=node['id']):
                if edge['type'] in ['CDG', 'RETURN']:
                    continue
                successor = self.pdg.ipdg.vs[edge.target]
                properties = successor.attributes()
                # print(node['text'], node['line'], '\n==>\n' + properties['text'], properties['line'], '\n' + edge['type'], edge['label'], '\n')
                # input()
                del properties['name']
                self.slice.add_vertex(successor['id'], **properties)
                if edge not in self.edges:
                    self.edges.add(edge)
                    self.slice.add_edge(node['id'], successor['id'], **edge.attributes())
                if edge['type'] == 'CALL':
                    cross_time -= 1
                if successor['id'] not in self.visit_id:
                    self.visit_id.add(successor['id'])
                    self.result_nodes.append(successor)
                    self.spread(successor, cross_time, 'forward')
        # dot = self.draw_graph(self.slice)
        # dot.render('pdf/slice', view=True, cleanup=True, format='pdf')
        # input()
        return

    @timer
    def get_slice(self, 
        startlines: List[int], 
        max_cross_time: int = 3
    ) -> None:
        startnodes = self.pdg.ipdg.vs.select(lambda x: x['line'] in startlines)
        for startnode in startnodes:
            properties = startnode.attributes()
            del properties['name']
            self.slice.add_vertex(startnode['id'], **properties)
            self.result_nodes.append(startnode)
            self.spread(startnode, 3, 'backward')
            self.visit_id.remove(startnode['id'])
            self.spread(startnode, 3, 'forward')
        dot = self.draw_graph(self.slice)
        dot.render('pdf/slice', view=True, cleanup=True, format='pdf')
        for node in self.result_nodes:
            print(node['text'], node['line'])

if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    slice = SLICE('c', code)
    slice.get_slice([88, 89, 90, 91, 92])
    