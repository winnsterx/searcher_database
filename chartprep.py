import datapane as dp
import plotly.graph_objects as go
from datetime import datetime
import seaborn as sns
import helpers
import secret_keys
import labels.searcher_addr_map as searcher_addr_map, labels.builder_addr_map as builder_addr_map
import attributes


def abbreviate_label(label, short=False):
    res = ""
    if label.startswith("0x"):
        if label in searcher_addr_map.SEARCHER_ADDR_LABEL_MAP:
            res = searcher_addr_map.SEARCHER_ADDR_LABEL_MAP[label]
            if short == False:
                res += " (" + label[:9] + ")"
            return res
        elif label in builder_addr_map.BUILDER_ADDR_MAP:
            res = builder_addr_map.BUILDER_ADDR_MAP[label]
            if short == False:
                res += " (" + label[:9] + ")"
            return res
        else:
            return label[:15] + ".."
    else:
        if len(label) < 15:
            return label
        else:
            return label[:15] + ".."


def convert_metric_for_title(metric):
    if metric == "tx":
        return "Transaction Count"
    elif metric == "vol":
        return "Volume (USD)"
    elif metric == "bribe":
        return "Bribes (Coinbase Transfers + Priority Fees, in ETH)"
    elif metric == "block":
        return "Block Count"


def get_unit_from_metric(metric):
    if metric == "tx":
        return "txs"
    elif metric == "vol":
        return "USD"
    elif metric == "bribe":
        return "ETH"


def get_builder_colors_map(list_of_builders):
    # colors = sns.color_palette("Paired", len(list_of_builders)).as_hex()
    colors = attributes.color_list
    top_builder_colors = attributes.top_color_list

    builder_color_map = {}
    i = 0

    for alias in builder_addr_map.extraData_builder_mapping.values():
        if i >= len(top_builder_colors):
            break
        builder_color_map[alias] = top_builder_colors[i]
        i += 1

    for idx, builder in enumerate(list_of_builders):
        if builder_color_map.get(builder) != None:
            continue
        color = colors[
            idx % len(colors)
        ]  # Wrap around if there are more builders than colors
        builder_color_map[builder] = color

    return builder_color_map


def create_searcher_builder_percentage_bar_chart(
    map, agg, mev_domain, metric, builder_color_map
):
    fig = go.Figure()
    top_searchers = helpers.slice_dict(agg, 25)
    builder_market_share = {}

    span = '<span style="font-size: 1.4rem;font-weight:bold; margin-bottom: 10px;">{} Searchers Flow Breakdown by Builder<br /><span style="font-size: 15px;">Ranked by Total {}</span></span>'

    for builder, searchers in map.items():
        builder_market_share[builder] = sum(searchers.values())

    total_count = sum(builder_market_share.values())
    unit = get_unit_from_metric(metric)
    for builder, searchers in map.items():
        x = []
        y = [abbreviate_label(s, True) for s in list(top_searchers.keys())]
        customdata = []
        # adding total market share as comparison
        y.insert(0, "All Searchers")
        x.insert(0, builder_market_share[builder] / total_count * 100)
        customdata.insert(
            0,
            (builder, helpers.humanize_number(builder_market_share[builder]), metric),
        )

        for searcher, _ in top_searchers.items():
            percent = searchers.get(searcher, 0) / agg[searcher] * 100
            x.append(percent)
            customdata.append(
                (builder, helpers.humanize_number(searchers.get(searcher, 0)), metric)
            )

        fig.add_trace(
            go.Bar(
                y=y[::-1],
                x=x[::-1],
                name=abbreviate_label(builder, True),
                text=[str(data[1]) + " " + unit for data in customdata[::-1]],
                textposition="auto",
                orientation="h",
                customdata=customdata[::-1],  # Your additional hover info
                hovertemplate=(
                    "<b>Searcher:</b> %{y}<br>"
                    "<b>Builder:</b> %{customdata[0]}<br>"
                    f"<b>Total %{{customdata[2]}} sent to builder:</b> %{{customdata[1]}} {unit}<br>"
                    "<b>Percentage:</b> %{x:.2r}%<extra></extra>"
                ),
                marker=dict(color=builder_color_map[builder], line=dict(width=1)),
            )
        )

    title_layout = {
        "text": span.format(
            mev_domain,
            convert_metric_for_title(metric)
            if metric != "bribe"
            else "Bribes (Coinbase Transfers + Priority Fees, in ETH)",
        ),
        "y": 0.9,
        "x": 0.05,
        "xanchor": "left",
        "yanchor": "top",
    }

    fig.update_layout(
        title=title_layout,
        xaxis=dict(ticksuffix="%", title=generate_xaxis_title(metric), range=[0, 100]),
        yaxis_title="Searcher Addresses",
        barmode="stack",
        legend={"traceorder": "normal"},
        margin={"t": 150, "l": 10},  # what gives the spacing between title and plot
        font=dict(family="Courier New, monospace", color="black"),
        height=850,
    )

    return fig


def create_searcher_pie_chart(agg, mev_domain, metric):
    small_searchers = {k: agg[k] for k in list(agg.keys())[30:]}
    agg = {k: agg[k] for k in list(agg)[:30]}
    agg.update({"Others": sum(small_searchers.values())})

    searchers = [abbreviate_label(s, True) for s in list(agg.keys())]
    counts = list(agg.values())
    unit = get_unit_from_metric(metric)
    fig = go.Figure(
        data=go.Pie(
            labels=searchers,
            values=counts,
            hole=0.3,  # Optional: to create a donut-like chart
            hovertemplate=(
                f"<b>Searcher:</b> %{{label}}<br>"
                f"<b>Value:</b> %{{value}} {unit}<br>"
                "<b>Percentage:</b> %{percent}<extra></extra>"
            ),
            textposition="inside",
            textinfo="percent",
        )
    )

    # Setting layout details
    fig.update_layout(
        title=generate_pie_title(metric, mev_domain),
        showlegend=True,
        font=dict(family="Courier New, monospace", color="black"),
        height=550,
    )
    return fig


def return_sorted_map_and_agg_pruned_of_known_entities_and_atomc(metric):
    """
    Returns atomic, nonatomic, and combined maps and aggs that are
    sorted, pruned of known entities, (for nonatomic, remove atomic addrs),
    and trimmed of only addrs responsible for 99% of {metric}
    """
    atomic_map = helpers.load_dict_from_json(
        f"atomic/fourteen/builder_atomic_maps/builder_atomic_map_{metric}.json"
    )

    atomic_agg = helpers.load_dict_from_json(f"atomic/fourteen/agg/agg_{metric}.json")

    nonatomic_map = helpers.load_dict_from_json(
        f"nonatomic/fourteen/builder_nonatomic_maps/builder_nonatomic_map_{metric}.json"
    )
    nonatomic_agg = helpers.load_dict_from_json(
        f"nonatomic/fourteen/agg/agg_{metric}.json"
    )

    # before, atomic_map is {total, arb,...}. after this, atomic is simple
    atomic_map = helpers.return_atomic_maps_with_only_type(atomic_map, "total")

    atomic_map, atomic_agg = helpers.prune_known_entities_from_map_and_agg(
        atomic_map, atomic_agg
    )

    atomic_map, atomic_agg = helpers.get_map_and_agg_in_range(
        atomic_map, atomic_agg, 0.99
    )
    # sort after pruning the known entities
    atomic_agg = helpers.sort_agg(atomic_agg)
    atomic_map = helpers.sort_map(atomic_map)

    nonatomic_map, nonatomic_agg = helpers.prune_known_entities_from_map_and_agg(
        nonatomic_map, nonatomic_agg
    )
    nonatomic_map, nonatomic_agg = helpers.remove_atomic_from_map_and_agg(
        nonatomic_map, nonatomic_agg, atomic_agg
    )
    nonatomic_map, nonatomic_agg = helpers.get_map_and_agg_in_range(
        nonatomic_map, nonatomic_agg, 0.99
    )

    nonatomic_agg = helpers.sort_agg(nonatomic_agg)
    nonatomic_map = helpers.sort_map(nonatomic_map)

    return [
        atomic_map,
        atomic_agg,
        nonatomic_map,
        nonatomic_agg,
    ]


def dump_data_used(all):
    # [block, tx, vol, bribe, vol_list]
    for i in range(0, len(all)):
        if i == 0:
            type = "tx"
        elif i == 1:
            type = "vol"
        elif i == 2:
            type = "bribe"
        all_maps_and_aggs = all[i]

        for j in range(0, len(all_maps_and_aggs), 2):
            map = all_maps_and_aggs[j]
            agg = all_maps_and_aggs[j + 1]
            if j == 0:
                mev_domain = "atomic"
            elif j == 2:
                mev_domain = "nonatomic"

            helpers.dump_dict_to_json(map, f"data/{type}/{mev_domain}_map_{type}.json")
            helpers.dump_dict_to_json(agg, f"data/{type}/{mev_domain}_agg_{type}.json")


def load_maps_and_aggs_from_dir(metric):
    path = f"data/{metric}/"
    atomic_map = helpers.load_dict_from_json(path + f"atomic_map_{metric}.json")
    nonatomic_map = helpers.load_dict_from_json(path + f"nonatomic_map_{metric}.json")

    atomic_agg = helpers.load_dict_from_json(path + f"atomic_agg_{metric}.json")
    nonatomic_agg = helpers.load_dict_from_json(path + f"nonatomic_agg_{metric}.json")

    return [
        atomic_map,
        atomic_agg,
        nonatomic_map,
        nonatomic_agg,
    ]


def add_dummy_traces_to_match(fig, target_num_traces):
    """Add dummy invisible traces to fig to match target_num_traces."""
    while len(fig.data) < target_num_traces:
        fig.add_trace(go.Bar(x=[], y=[], visible=False))
    return fig


def generate_title(metric, mev_domain):
    span = '<span style="font-size: 1.4rem;font-weight:bold; margin-bottom: 10px;">{} Searchers Flow Breakdown by Builder<br /><span style="font-size: 15px;">Ranked by {}</span></span>'
    title = span.format(mev_domain, convert_metric_for_title(metric))
    return title


def generate_pie_title(metric, mev_domain):
    span = '<span style="font-size: 1.4rem;font-weight:bold; margin-bottom: 10px;">{} Searchers Market Share<br /><span style="font-size: 15px;">Measured by {}</span></span>'
    title = span.format(mev_domain, convert_metric_for_title(metric))
    return title


def generate_xaxis_title(metric):
    if metric == "vol":
        return "Percentage of Volume"
    elif metric == "bribe":
        return "Percentage of Total Bribes"
    elif metric == "tx":
        return "Percentage of Transactions"


def create_bar_charts_with_toggle(
    fig_prime, fig_bribe, fig_sec, metric, metric_sec, mev_domain
):
    # Combine the figures. Set the other ones as invisible initially.
    max_traces = max(len(fig_prime.data), len(fig_bribe.data), len(fig_sec.data))

    # Add dummy traces to each figure to match the maximum number of traces
    fig_prime = add_dummy_traces_to_match(fig_prime, max_traces)
    fig_bribe = add_dummy_traces_to_match(fig_bribe, max_traces)
    fig_sec = add_dummy_traces_to_match(fig_sec, max_traces)

    # Combine and set the toggle logic
    combined_fig = fig_prime
    for trace in fig_bribe.data:
        trace.visible = False
        combined_fig.add_trace(trace)

    for trace in fig_sec.data:
        trace.visible = False
        combined_fig.add_trace(trace)

    combined_fig.update_layout(
        updatemenus=[
            {
                "type": "dropdown",
                "direction": "down",
                "active": 0,
                "showactive": True,
                "x": 1.3,
                "y": 1.08,
                "xanchor": "right",
                "yanchor": "bottom",
                "buttons": [
                    {
                        "label": convert_metric_for_title(metric),
                        "method": "update",
                        "args": [
                            {
                                "visible": [True] * max_traces
                                + [False] * max_traces
                                + [False] * max_traces
                            },
                            {
                                "title": {
                                    "text": generate_title(metric, mev_domain),
                                    "y": 0.9,
                                    "x": 0.05,
                                    "xanchor": "left",
                                    "yanchor": "top",
                                },
                                "xaxis.title.text": generate_xaxis_title(metric),
                            },
                        ],
                    },
                    {
                        "label": "Bribes (ETH)",
                        "method": "update",
                        "args": [
                            {
                                "visible": [False] * max_traces
                                + [True] * max_traces
                                + [False] * max_traces
                            },
                            {
                                "title": {
                                    "text": generate_title("bribe", mev_domain),
                                    "y": 0.9,
                                    "x": 0.05,
                                    "xanchor": "left",
                                    "yanchor": "top",
                                },
                                "xaxis.title.text": generate_xaxis_title("bribe"),
                            },
                        ],
                    },
                    {
                        "label": convert_metric_for_title(metric_sec),
                        "method": "update",
                        "args": [
                            {
                                "visible": [False] * max_traces
                                + [False] * max_traces
                                + [True] * max_traces
                            },
                            {
                                "title": {
                                    "text": generate_title(metric_sec, mev_domain),
                                    "y": 0.9,
                                    "x": 0.05,
                                    "xanchor": "left",
                                    "yanchor": "top",
                                },
                                "xaxis.title.text": generate_xaxis_title(metric_sec),
                            },
                        ],
                    },
                ],
            }
        ]
    )
    return combined_fig


def create_pie_charts_with_toggle(
    fig_prime, fig_bribe, fig_sec, metric, metric_sec, mev_domain
):
    combined_fig = fig_prime
    for trace in fig_bribe.data:
        trace.visible = False
        combined_fig.add_trace(trace)

    for trace in fig_sec.data:
        trace.visible = False
        combined_fig.add_trace(trace)

    # Create a dropdown for the toggle effect
    combined_fig.update_layout(
        updatemenus=[
            {
                "type": "dropdown",
                "direction": "down",
                "active": 0,
                "showactive": True,
                "x": 1.25,
                "y": 1.08,
                "xanchor": "right",
                "yanchor": "bottom",
                "buttons": [
                    {
                        "label": convert_metric_for_title(metric),
                        "method": "update",
                        "args": [
                            {"visible": [True, False, False]},
                            {
                                "title": {
                                    "text": generate_pie_title(metric, mev_domain),
                                    "y": 0.9,
                                    "x": 0.05,
                                    "xanchor": "left",
                                    "yanchor": "top",
                                },
                            },
                        ],
                    },
                    {
                        "label": "Bribes (ETH)",
                        "method": "update",
                        "args": [
                            {"visible": [False, True, False]},
                            {
                                "title": {
                                    "text": generate_pie_title(metric, mev_domain),
                                    "y": 0.9,
                                    "x": 0.05,
                                    "xanchor": "left",
                                    "yanchor": "top",
                                },
                            },
                        ],
                    },
                    {
                        "label": convert_metric_for_title(metric_sec),
                        "method": "update",
                        "args": [
                            {"visible": [False, False, True]},
                            {
                                "title": {
                                    "text": generate_pie_title(metric_sec, mev_domain),
                                    "y": 0.9,
                                    "x": 0.05,
                                    "xanchor": "left",
                                    "yanchor": "top",
                                },
                            },
                        ],
                    },
                ],
            }
        ]
    )

    return combined_fig


def create_html_page():
    all_builders_keys = list(
        helpers.load_dict_from_json(
            "nonatomic/fourteen/builder_nonatomic_maps/builder_nonatomic_map_block.json"
        ).keys()
    )

    builder_color_map = get_builder_colors_map(all_builders_keys)

    all_maps_and_aggs_tx = return_sorted_map_and_agg_pruned_of_known_entities_and_atomc(
        "tx"
    )
    all_maps_and_aggs_vol = (
        return_sorted_map_and_agg_pruned_of_known_entities_and_atomc("vol")
    )

    all_maps_and_aggs_bribe = (
        return_sorted_map_and_agg_pruned_of_known_entities_and_atomc("bribe")
    )

    dump_data_used(
        [
            all_maps_and_aggs_tx,
            all_maps_and_aggs_vol,
            all_maps_and_aggs_bribe,
        ]
    )

    nonatomic_vol_bar = create_searcher_builder_percentage_bar_chart(
        all_maps_and_aggs_vol[2],
        all_maps_and_aggs_vol[3],
        "Non-atomic",
        "vol",
        builder_color_map,
    )


    nonatomic_bribe_bar = create_searcher_builder_percentage_bar_chart(
        all_maps_and_aggs_bribe[2],
        all_maps_and_aggs_bribe[3],
        "Non-atomic",
        "bribe",
        builder_color_map,
    )

    nonatomic_tx_bar = create_searcher_builder_percentage_bar_chart(
        all_maps_and_aggs_tx[2],
        all_maps_and_aggs_tx[3],
        "Non-atomic",
        "tx",
        builder_color_map,
    )

    nonatomic_bar = create_bar_charts_with_toggle(
        nonatomic_tx_bar,
        nonatomic_bribe_bar,
        nonatomic_vol_bar,
        "tx",
        "vol",
        "Non-atomic",
    )

    atomic_tx_bar = create_searcher_builder_percentage_bar_chart(
        all_maps_and_aggs_tx[0],
        all_maps_and_aggs_tx[1],
        "Atomic",
        "tx",
        builder_color_map,
    )

    atomic_bribe_bar = create_searcher_builder_percentage_bar_chart(
        all_maps_and_aggs_bribe[0],
        all_maps_and_aggs_bribe[1],
        "Atomic",
        "bribe",
        builder_color_map,
    )

    atomic_vol_bar = create_searcher_builder_percentage_bar_chart(
        all_maps_and_aggs_vol[0],
        all_maps_and_aggs_vol[1],
        "Atomic",
        "vol",
        builder_color_map,
    )

    atomic_bar = create_bar_charts_with_toggle(
        atomic_tx_bar, atomic_bribe_bar, atomic_vol_bar, "tx", "vol", "Atomic"
    )

    atomic_searcher_pie_tx = create_searcher_pie_chart(
        all_maps_and_aggs_tx[1],
        "Atomic",
        "tx",
    )

    atomic_searcher_pie_bribe = create_searcher_pie_chart(
        all_maps_and_aggs_bribe[1],
        "Atomic",
        "bribe",
    )
    atomic_searcher_pie_vol = create_searcher_pie_chart(
        all_maps_and_aggs_vol[1],
        "Atomic",
        "vol",
    )
    atomic_pie = create_pie_charts_with_toggle(
        atomic_searcher_pie_tx,
        atomic_searcher_pie_bribe,
        atomic_searcher_pie_vol,
        "tx",
        "vol",
        "Atomic",
    )

    nonatomic_searcher_pie_vol = create_searcher_pie_chart(
        all_maps_and_aggs_vol[3],
        "Non-atomic",
        "vol",
    )

    nonatomic_searcher_pie_bribe = create_searcher_pie_chart(
        all_maps_and_aggs_bribe[3],
        "Non-atomic",
        "bribe",
    )
    nonatomic_searcher_pie_tx = create_searcher_pie_chart(
        all_maps_and_aggs_tx[3],
        "Non-atomic",
        "tx",
    )

    nonatomic_pie = create_pie_charts_with_toggle(
        nonatomic_searcher_pie_tx,
        nonatomic_searcher_pie_bribe,
        nonatomic_searcher_pie_vol,
        "tx",
        "vol",
        "Non-atomic",
    )

    title = "# <p style='text-align: center;margin:0px;'> Searcher-Builder Relationship Dashboard </p>"
    head = (
        "<div><div><div style ='float:left;color:#0F1419;font-size:18px'>Based on transactions from last 14 days. Last updated {}.</div>"
        + '<div style ="float:right;font-size:18px;color:#0F1419">View <a href="https://github.com/winnsterx/searcher_database/tree/main/data">raw data</a> </div></div>'
        + '<div><div style ="float:left;font-size:18px;color:#0F1419;clear: left">Built by '
        + '<a href="https://twitter.com/winnsterx">Winnie</a> at <a href="https://twitter.com/BitwiseInvest">Bitwise</a>. Inspired by '
        + '<a href="https://mevboost.pics">mevboost.pics</a>.</div>'
        + '<div style ="float:right;font-size:18px;color:#0F1419">View Source on <a href="https://github.com/winnsterx/searcher_database">Github</a></div></div></div><br/><br/>'
        + "\n"
    )
    head = head.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    nonatomic_intro = """
    <div style='background-color: white; padding: 2rem; margin-top: 2rem; border-radius: 1rem; border: 3px solid #4c51ff;'>
        <strong>Non-atomic MEV</strong> refers to mostly CEX-DEX arbitrage.<br><br>
        Using <a href="https://data.zeromev.org/docs/" style="color: #4c51ff;">Zeromev API</a>, we collect all directional swaps and identify non-atomic MEV transactions using these <a href="https://github.com/winnsterx/searcherbuilder.pics/blob/e084727a0bf09f990d1aef090a4aef7e3df78b72/nonatomic_mev.py#L19" style="color: #4c51ff;">heuristics</a>. We filter out transactions sent to <a href="https://github.com/winnsterx/searcherbuilder.pics/blob/main/labels/non_mev_contracts.py" style="color: #4c51ff;">known non-MEV smart contracts</a>. Examining the flow that non-atomic searchers sent to each builder, we can infer potentially exclusive searcher-builder relationships. We recommend <strong>volume</strong> and <strong>bribe</strong> as the most reliable metric for non-atomic MEV. The figures presented here are strictly <strong>lower-bound</strong>.
    </div>
    """

    atomic_intro = """
    <div style='background-color: white; padding: 2rem; margin-top: 2rem; border-radius: 1rem; border: 3px solid #4c51ff;'>
        <strong>Atomic MEV</strong> refers to <strong>DEX-DEX arbitrage, sandwiching, and liquidation.</strong><br><br>
        Using <a href="https://data.zeromev.org/docs/" style="color: #4c51ff;">Zeromev API</a>, we identify DEX-DEX arbitrage, sandwiching, and liquidation transactions. We filter out transactions sent to <a href="https://github.com/winnsterx/searcherbuilder.pics/blob/main/labels/non_mev_contracts.py" style="color: #4c51ff;">known non-MEV smart contracts</a>. Examining the flow that atomic searchers sent to each builder, we can infer potentially exclusive searcher-builder relationships. We recommend <strong>transaction count</strong> and <strong>bribe</strong> as the most reliable metric for atomic MEV. The figures presented here are strictly <strong>lower-bound</strong>.
    </div>
    """

    view = dp.Blocks(
        dp.Page(
            title="Non-atomic MEV",
            blocks=[
                title,
                head,
                nonatomic_intro,
                nonatomic_bar,
                nonatomic_pie,
            ],
        ),
        dp.Page(
            title="Atomic MEV",
            blocks=[
                title,
                head,
                atomic_intro,
                atomic_bar,
                atomic_pie,
            ],
        ),
    )
    dp.save_report(view, path=secret_keys.HTML_PATH + "/index.html")

    fixedposi = (
        "<style>nav.min-h-screen {position: -webkit-sticky;position: sticky;}</style>"
    )

    more_css = """
        <style>
        
        body {
            max-width: 900px;
            margin-left: auto !important;
            margin-right: auto !important;
            background: #eee;
        }
        @media screen and (min-width: 700px) {
            body {
                max-width: 1000px;
            }
        }

        a.pt-1 {
            position: sticky;
            top:0%;
            font-size: 1.6rem;
            padding-top: 1.2rem !important;
            padding-bottom: 1.2rem !important;
        }

        nav div, nav div.hidden {
            margin: 0 0 0 0;
            width: 100%;
            justify-content: space-evenly;
        }
        .py-5.px-4 {
            background: white;
        }

        main.w-full {
            padding-bottom: 0; !important;
        }
        main div.px-4 {
            background: #eee;
        }


        .flex {
            width: 100%; 
            justify-content: space-evenly;
        }

        nav {
            position: sticky;
            top: 0;
            z-index: 99999;
            background-color: white;
            display: flex;
            margin-bottom: 1.5rem;
        }

        div.justify-start {
            margin-top: 1rem;
            margin-bottom: 1rem;
        }
                
        </style>
    """

    with open(secret_keys.HTML_PATH + "/index.html", "r") as file:
        f = file.read()

    # Direct URL to the raw image on GitHub
    twitter_image_url = "https://raw.githubusercontent.com/winnsterx/winnsterx.github.io/main/preview.png"

    # Replace the existing twitter:image and og:image content with the new URL
    OG_STUFF = f""" <title>searcherbuilder.pics | Searcher Builder Dashboard</title>
    <meta charset="UTF-8" />
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@winnsterx">
    <meta name="twitter:title" content="Searcher Builder Dashboard">
    <meta name="twitter:description" content="Selected comparative visualizations on searcher-builder relationship on Ethereum.">
    <meta name="twitter:image" content="{twitter_image_url}">
    <meta property="og:title" content="Searcher Builder Dashboard">
    <meta property="og:site_name" content="searcherbuilder.pics">
    <meta property="og:url" content="https://www.searcherbuilder.pics/">
    <meta property="og:description" content="Selected comparative visualizations on searcher-builder relationship on Ethereum.">
    <meta property="og:type" content="website">
    <link rel="shortcut icon" href="https://mevboost.toniwahrstaetter.com/ethlogo.png" />
    <meta property="og:image" content="{twitter_image_url}">
    <meta name="description" content="Up-to-date comparative visualizations on MEV-Boost and Proposer Builder Separation on Ethereum.">
    <meta name="keywords" content="Ethereum, MEV-Boost, PBS, Dashboard">
    <meta name="author" content="Toni Wahrstätter">"""

    f = f.replace('<meta charset="UTF-8" />\n', fixedposi + OG_STUFF + more_css)  # Assuming fixedposi and more_css are defined previously

    with open(secret_keys.HTML_PATH + "/index.html", "w") as file:
        file.write(f)

if __name__ == "__main__":
    create_html_page()
