from CFG import *
import copy

def reverse(cfg):
    reverse_cfg = copy.deepcopy(cfg)
    reverse_cfg.delete_edges(reverse_cfg.get_edgelist())
    for edge in cfg.es:
        source, target, label = edge.source, edge.target, edge['label']
        reverse_cfg.add_edge(target, source, label=label)
    exit_node = reverse_cfg.vs.find(type='function_exit')
    func_node = reverse_cfg.vs.find(type='function_definition')
    reverse_cfg.add_edge(exit_node, func_node, label='')  # 添加一个从Exit到函数入口的边
    return reverse_cfg

def get_subTree(cfg):   # 按照广度优先遍历，找出一个子树
    exit_node = cfg.vs.find(type='function_exit')
    visited = {v.index:False for v in cfg.vs}
    queue = [exit_node]
    visited[exit_node] = True
    subTree = copy.deepcopy(cfg)
    subTree.delete_edges(subTree.get_edgelist())
    while queue:
        node = queue.pop()
        if not cfg.successors(node):
            continue
        for succ in cfg.successors(node):
            if not visited[succ]:
                queue.append(succ)
                visited[succ] = True
                subTree.add_edge(node, succ, label='')
    return subTree

def post_dominator_tree(cfg, subTree):  # 生成后支配树
    PDT = copy.deepcopy(subTree)
    changed = True
    exit_node = cfg.vs.find(type='function_exit')
    while changed:
        changed = False
        for v in cfg.vs:
            if v['type'] == 'function_exit':
                continue
            for u in cfg.predecessors(v.index):
                parent_v = PDT.predecessors(v.index)[0]
                # 寻找这两个节点的最近公共祖先
                v_path = PDT.get_shortest_paths(exit_node.index, parent_v)
                u_path = PDT.get_shortest_paths(exit_node.index, u)
                v_lines = [PDT.vs[i].index for i in v_path[0]]
                u_lines = [PDT.vs[i].index for i in u_path[0]]
                for a, b in zip(v_lines, u_lines):
                    if a != b:
                        break
                    lca = a
                if u != parent_v and parent_v != lca:
                    PDT.add_edge(lca, v.index)
                    PDT.delete_edges(PDT.get_eid(parent_v, v.index))
                    changed = True
    return PDT

def dominance_frontier(reverse_cfg, PDT):   # 计算支配边界
    CDG = copy.deepcopy(reverse_cfg)
    CDG.delete_edges(CDG.get_edgelist())
    for v in reverse_cfg.vs:
        preds = reverse_cfg.predecessors(v)
        if len(preds) >= 2:     # 有多个分支
            for runner in preds:
                while runner != PDT.predecessors(v)[0]:
                    CDG.add_edge(v.index, runner)
                    runner = PDT.predecessors(runner)[0]
    return CDG
        
class CDG:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cdgs = {}

    @timer
    def construct_cdg(self):
        # 参考文章 https://blog.csdn.net/Dong_HFUT/article/details/121492818?spm=wolai.workspace.0.0.477036c4rNeEPV
        for funcname, cfg in self.cfg.cfgs.items():
            print(f'constructing CDG for {funcname:>40}', end='\r')
            reverse_cfg = reverse(cfg)
            subTree = get_subTree(reverse_cfg)
            PDT = post_dominator_tree(reverse_cfg, subTree)
            CDG = dominance_frontier(reverse_cfg, PDT)
            self.cdgs[funcname] = CDG
        print(f'{"finish constructing CDG":-^70}')

    def see_graph(self, pdf=True, view=True):
        self.construct_cdg()
        for funcname, cdg in self.cdgs.items():
            dot = Digraph(strict=True)
            exit_node = cdg.vs.find(type='function_exit')
            cdg.delete_vertices(exit_node.index)
            for node in cdg.vs:
                label = html.escape(node['text']) + '\\n' + f"{node['type']} | {node.index}"
                if node['is_branch']:
                    dot.node(node['id'], shape='diamond', label=label, fontname='fangsong')
                elif node['type'] == 'function_definition':
                    dot.node(node['id'], label=label, fontname='fangsong')
                elif node['type'] == 'function_exit':
                    dot.node(node['id'], label='exit | ' + str(node.index), fontname='fangsong')
                else:
                    dot.node(node['id'], shape='rectangle', label=label, fontname='fangsong')
            for edge in cdg.es:
                next_node, label = edge.target, edge['label'] if 'label' in edge.attributes() else ''
                dot.edge(cdg.vs[edge.source]['id'], cdg.vs[next_node]['id'], label=label)
            if pdf:
                dot.render(f'pdf/{funcname}', view=view, cleanup=True, format='pdf')
                dot.clear()

if __name__ == '__main__':
    code = r'{}'.format(open('test.c', 'r', encoding='utf-8').read())
    cfg = CFG('c', code)
    cfg.construct_cfg()
    cdg = CDG(cfg)
    cdg.see_graph(view=True)

