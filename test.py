from igraph import Graph
from graphviz import Digraph
import igraph

# 随机生成一个图
g = Graph(directed=True)
g1 = Graph(directed=True)

g.add_vertex('one', id=1)
g.add_vertex('two', id=2)
g.add_vertex('three', id=3)
g.add_vertex('four', id=4)
# g.add_edge('one', 'two', label='one-two')
# g.add_edge('two', 'three', label='two-three')
# g.add_edge('three', 'four', label='three-four')

edges = [('one','two'), ('two','three'), ('three','four')]
property = {'label': ['one-two', 'two-three', 'three-four']}
g.add_edges(edges, property)
print(g.vs['one'].out_edges())

# g1.add_vertex('three', id=3)
# g1.add_vertex('five', id=5)
# g1.add_vertex('six', id=6)
# g1.add_vertex('seven', id=7)
# g1.add_vertex('eight', id=8)
# g1.add_edge('five', 'six', label='five-six')
# g1.add_edge('six', 'seven', label='six-seven')
# g1.add_edge('seven', 'eight', label='seven-eight')

def draw(graph):
    dot = Digraph()
    for node in graph.vs:
        label = node['name']
        dot.node(node['name'], label=label)
    for edge in graph.es:
        dot.edge(graph.vs[edge.source]['name'], graph.vs[edge.target]['name'], label=edge['label'])
    dot.render('pdf/graph', view=True, cleanup=True)

# def print_graph(graph):
#     for node in graph.vs:
#         print(node.index, node.attributes())
#     for edge in graph.es:
#         print(edge.index, graph.vs[edge.source]['name'], graph.vs[edge.target]['name'], edge.attributes())
#     print('---------------------------------')
# print(g)
# print(g1)
# u = g.union(g1)

# u.add_edge('four', 'five', label='four-five')
draw(g)
# # print(u)
# # print_graph(g)
# # print_graph(g1)
# # print_graph(u)

# help(igraph.Graph.union)