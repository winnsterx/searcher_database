import datapane as dp
import plotly.graph_objects as go
from datetime import datetime
import analysis 
import visual_analysis

def abbreviate_label(label):
    if label.startswith("0x"):
        return label[:9] + '...' if len(label) > 10 else label
    else: 
        return label


def create_searcher_builder_sankey(map, agg, title, unit):
    # nodes is index of searcher + builder, each unique
    # an entity will now be recognized as the index from this list now
    span = '<span style="font-size: 24px;font-weight:bold;">{}</span>'     
    searcher_builder_map = analysis.create_searcher_builder_map(map)
    # nodes = sorted_searchers + list(map.keys())
    nodes = list(agg.keys()) + list(map.keys())
    abbreviated_nodes = [abbreviate_label(node) for node in nodes]
    source_indices = []
    target_indices = [] 
    values = []

    for searcher, builders in searcher_builder_map.items():
        for builder, count in builders.items():
            source_indices.append(nodes.index(searcher))
            target_indices.append(nodes.index(builder))
            values.append(count)

    x_coors = [0.001] * len(agg) + [0.999] * len(map)
    y_coors = [0.01] * len(agg) + [0.01] * len(map)

    fig = go.Figure(data=go.Sankey(
        arrangement='snap',
        node = dict(
            x = x_coors,
            y = y_coors,
            pad = 20,
            thickness = 20,
            line = dict(color = "black", width = 0.5),      
            label = abbreviated_nodes,  
            hovertemplate='<b>%{label}<b><br />%{value}'+unit,
        ),
        link = dict(
            source = source_indices,
            target = target_indices,
            value = values,            
            hovertemplate='<b>%{source.value:,.0f} <br /><b>'+unit,  
        )
    ))

    fig.update_layout(title_text=span.format(title),
                      font_size=16,
                      paper_bgcolor='#eee',
                      font=dict(
                                family="Courier New, monospace",
                                size=20,  # Set the font size here
                                color="black"
                               ), autosize=False, width=800, height=1500)
    return fig 

def prune_map_and_agg_for_sankey(map, agg, metric, percentile, min_count, is_atomic):
    # map, agg are non sorted, native maps from atomic or nonatomic
    if is_atomic:
        map = analysis.return_atomic_maps_with_only_type(map, "total")
    else:
        atomic = analysis.load_dict_from_json(f"atomic/new/agg/agg_{metric}.json")
        agg = analysis.remove_atomic_from_agg(agg, atomic)
        map = analysis.remove_atomic_from_map(map, atomic)
    # get searchers that are responsible for x% of all {metric} produced 
    map, agg = analysis.get_map_and_agg_in_range(map, agg, percentile)
    # eliminate smaller builders who account for little of a tx to show better correlation
    map, agg = analysis.remove_small_builders(map, agg, min_count)
    return map, agg


if __name__ == "__main__":
    nonatomic_map = analysis.sort_map(analysis.load_dict_from_json("nonatomic/new/builder_swapper_maps/builder_swapper_map_vol.json"))
    nonatomic_agg = analysis.load_dict_from_json("nonatomic/new/agg/agg_vol.json")
    nonatomic_map, nonatomic_agg = prune_map_and_agg_for_sankey(nonatomic_map, nonatomic_agg, "vol", 0.9, 1000, False)
    analysis.dump_dict_to_json(nonatomic_map, "used_map.json")
    analysis.dump_dict_to_json(nonatomic_agg, "used_agg.json")
    nonatomic_fig = create_searcher_builder_sankey(nonatomic_map, nonatomic_agg, "Non-atomic Searcher-Builder Orderflow by Volume (USD, last month)", "USD")

    atomic_map = analysis.load_dict_from_json("atomic/new/builder_atomic_maps/builder_atomic_map_tx.json")
    atomic_agg = analysis.load_dict_from_json("atomic/new/agg/agg_tx.json")
    atomic_map, atomic_agg = prune_map_and_agg_for_sankey(atomic_map, atomic_agg, "tx", 0.9, 5, True)
    atomic_map = analysis.sort_map(atomic_map)
    atomic_fig = create_searcher_builder_sankey(atomic_map, atomic_agg, "Atomic Searcher-Builder Orderflow by Tx Count (USD, last month)", "txs")


    title = "# <p style='text-align: center;margin:0px;'> __Searcher Transparency Dashboard__ </p>"
    head =  '<div><div style ="float:left;font-size:18px;color:#0F1419;clear: left">Built by '\
            +'<a href="https://twitter.com/winnsterx">winnsterx</a></div>'\
            +'<div style ="float:right;font-size:18px;color:#0F1419">View Source on Github'\
            +'<a href="https://github.com/winnsterx/searcher_database>Github</a></div></div>'
    
    # atomic_fig.show()
    view = dp.Blocks(
        dp.Page(title="Highlights", blocks=[
            title, 
            head, 
            nonatomic_fig,
            atomic_fig
        ]),
        dp.Page(title="Volume", blocks=[
            nonatomic_fig,
            atomic_fig
        ]),
        dp.Page(title="Number of Txs", blocks=[
            nonatomic_fig,
            atomic_fig
        ]),
        dp.Page(title="Bribes", blocks=[
            nonatomic_fig,
            atomic_fig
        ])
    )
    dp.save_report(view, path="/Users/winniex/Documents/GitHub/winnsterx.github.io/index.html")
