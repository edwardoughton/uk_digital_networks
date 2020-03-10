"""
Define core network.

Written by Ed Oughton

"""
import os
import sys
import configparser
import csv
import fiona
import time

from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import  cascaded_union
import networkx as nx

from rtree import index

from collections import OrderedDict

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_RAW = os.path.join(BASE_PATH, 'raw')
DATA_INTERMEDIATE = os.path.join(BASE_PATH, 'intermediate')


def read_existing_nodes(path):
    """
    Load in the existing node data.

    """
    output = []

    with fiona.open(path, 'r') as source:
        for item in source:
            if not item['properties']['OLO'] is None:
                output.append({
                    'type': item['type'],
                    'geometry': item['geometry'],
                    'properties': {
                        'OLO': item['properties']['OLO'],
                        'population': item['properties']['population'],
                    }
                })

    return output


def read_lookup(path):
    """
    Import lookup of BT 21CN core node locations.

    """
    output = []

    with open(path, 'r') as source:
        reader = csv.DictReader(source)
        for item in reader:
            if not item['area'] == 'Belfast':
                output.append({
                    'node': item['node'],
                    'area': item['area'],
                    'OLO': item['OLO'],
                    'inner': item['inner'],
                    'outer': item['outer'],
                    'metro': item['metro'],
                    'tier_1': 0,
                    'msan': 0,
                })

    return output

def determine_nodes(exchanges, lookup):
    """

    """
    output = []

    inner_list = return_list(lookup, 'inner', '1')
    outer_list = return_list(lookup, 'outer', '1')
    metro_list = return_list(lookup, 'metro', '1')

    for exchange in exchanges:

        if exchange['properties']['OLO'] in inner_list:
            inner = 1
            lower = 0
        else:
            inner = 0


        if exchange['properties']['OLO'] in outer_list:
            outer = 1
            lower = 0
        else:
            outer = 0


        if exchange['properties']['OLO'] in metro_list:
            metro = 1
            lower = 1
        else:
            metro = 0

        output.append({
            'type': exchange['type'],
            'geometry': exchange['geometry'],
            'properties': {
                'OLO': exchange['properties']['OLO'],
                'population': exchange['properties']['population'],
                'inner': inner,
                'outer': outer,
                'metro': metro,
                'tier_1': 0,
                'msan': 0,
                'lower': lower
            }
        })

    return output

def return_list(nodes, key, value):
    """

    """
    output = []

    for item in nodes:
        if item[key] == value:
            output.append(item['OLO'])

    return output


def import_islands(path):
    """
    Load in lookup for islands.

    """
    output = []

    with open(path, 'r') as source:
        reader = csv.DictReader(source)
        for item in reader:
            output.append({
                'OLO': item['olo'],
                'island': item['island'],
            })

    return output


def process_islands(exchanges, islands_lut):
    """
    Segment echanges into islands and then create a set of edges.

    """
    island_names = set()
    for exchange in islands_lut:
        island_names.add(exchange['island'])

    all_island_exchanges = []
    arran_set = set()
    campbeltown_set = set()
    islay_set = set()
    mull_set = set()
    orkney_set = set()
    outer_heb_set = set()
    shetland_set = set()
    skye_set = set()

    for island in island_names:
        for exchange in islands_lut:
            if island == exchange['island']:
                all_island_exchanges.append(exchange['OLO'])
                locals()['{}_set'.format(island)].add(exchange['OLO'])

    arran = []
    campbeltown = []
    islay = []
    mull = []
    orkney = []
    outer_heb = []
    shetland = []
    skye = []

    island_exchanges = []
    for island in island_names:
        for exchange in exchanges:
            if exchange['properties']['OLO'] in locals()['{}_set'.format(island)]:
                exchange['properties']['island'] = island
                locals()[island].append(exchange)

    links = []
    for island in list(island_names):

        new_links = []

        spanning_tree = design_network(locals()['{}'.format(island)])

        for link in spanning_tree:
            new_links.append({
                'type': 'Feature',
                'geometry': link['geometry'],
                'properties': {
                    'source': link['properties']['from'],
                    'sink': link['properties']['to'],
                    'population': 0,
                    'level': 'unknown',
                    'inner': 'unknown',
                    'outer': 'unknown',
                    'metro': 'unknown',
                    'tier_1': 'unknown',
                    'msan': 'unknown',
                }
            })

        links = links + new_links

    exchanges_minus_islands = []
    island_exchanges = []

    for exchange in exchanges:
        if exchange['properties']['OLO'] not in list(all_island_exchanges):
            exchanges_minus_islands.append(exchange)
        if exchange['properties']['OLO'] in list(all_island_exchanges):
            island_exchanges.append(exchange)

    return exchanges_minus_islands, island_exchanges, links


def design_network(nodes):

    links = []

    edges = []
    for node1_id, node1 in enumerate(nodes):
        for node2_id, node2 in enumerate(nodes):
            if node1_id != node2_id:
                geom1 = Point(node1['geometry']['coordinates'])
                geom2 = Point(node2['geometry']['coordinates'])
                line = LineString([geom1, geom2])
                edges.append({
                    'type': 'Feature',
                    'geometry': mapping(line),
                    'properties':{
                        'from': node1['properties']['OLO'],
                        'to':  node2['properties']['OLO'],
                        'length': line.length,
                    }
                })

    G = nx.Graph()

    for node in nodes:
        G.add_node(node['properties']['OLO'], object=node)

    for edge in edges:
        G.add_edge(edge['properties']['from'], edge['properties']['to'],
            object=edge, weight=edge['properties']['length'])

    tree = nx.minimum_spanning_edges(G)

    for branch in tree:
        link = branch[2]['object']
        if link['properties']['length'] > 0:
            links.append(link)

    return links


def connect(exchanges, islands, islands_lut):
    """

    """
    output = []

    inner = []
    outer = []
    metro = []
    tier_1 = []
    msan = []
    lower = []

    for exchange in exchanges:

        coords = shape(exchange['geometry'])

        if int(exchange['properties']['inner']) > 0:
            inner.append(exchange)

        if (int(exchange['properties']['outer']) > 0 or int(exchange['properties']['inner']) > 0):
            outer.append(exchange)

        if int(exchange['properties']['metro']) > 0:
            metro.append(exchange)

        if int(exchange['properties']['lower']) > 0:
            lower.append(exchange)

    ranked = sorted(lower, reverse = True, key=lambda x: x['properties']['population'])[:1000]

    tier_1_ids = [e['properties']['OLO'] for e in ranked]

    for exchange in lower:
        if exchange['properties']['OLO'] in tier_1_ids:
            tier_1.append({
                'type': exchange['type'],
                'geometry': exchange['geometry'],
                'properties': {
                    'OLO': exchange['properties']['OLO'],
                    'population': exchange['properties']['population'],
                    'inner': exchange['properties']['inner'],
                    'outer': exchange['properties']['outer'],
                    'metro': exchange['properties']['metro'],
                    'tier_1': 1,
                    'msan': exchange['properties']['msan'],
                    'lower': exchange['properties']['lower'],
                }
            })
        if not exchange['properties']['OLO'] in tier_1_ids:
            msan.append({
                'type': exchange['type'],
                'geometry': exchange['geometry'],
                'properties': {
                    'OLO': exchange['properties']['OLO'],
                    'population': exchange['properties']['population'],
                    'inner': exchange['properties']['inner'],
                    'outer': exchange['properties']['outer'],
                    'metro': exchange['properties']['metro'],
                    'tier_1': exchange['properties']['tier_1'],
                    'msan': 1,
                    'lower': exchange['properties']['lower'],
                }
            })

    print(len(msan), len(tier_1), len(metro), len(outer), len(inner))

    idx_inner_core = index.Index()
    for exchange in inner:
        coords = shape(exchange['geometry'])
        idx_inner_core.insert(0, coords.bounds, exchange)

    idx_all_core = index.Index()
    for exchange in outer:
        coords = shape(exchange['geometry'])
        idx_all_core.insert(0, coords.bounds, exchange)

    idx_metro = index.Index()
    for exchange in metro:
        coords = shape(exchange['geometry'])
        idx_metro.insert(0, coords.bounds, exchange)

    idx_tier_1 = index.Index()
    for exchange in tier_1:
        coords = shape(exchange['geometry'])
        idx_tier_1.insert(0, coords.bounds, exchange)

    idx_all = index.Index()
    for exchange in exchanges:
        coords = shape(exchange['geometry'])
        idx_all.insert(0, coords.bounds, exchange)

    exchanges = metro + msan + tier_1

    for exchange in exchanges:

        geom = shape(exchange['geometry'])

        if int(exchange['properties']['inner']) > 0:

            closest_nodes =  list(
                idx_inner_core.nearest(
                    coords.bounds,
                    len(inner)+1,
                    objects='raw')
                    )

            for node_1 in closest_nodes:

                coords_node_1 = shape(node_1['geometry'])

                for node_2 in closest_nodes:

                    coords_node_2 = shape(node_2['geometry'])

                    output.append({
                        'type': exchange['type'],
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': [
                                list(coords_node_1.coords)[0],
                                list(coords_node_2.coords)[0]]
                        },
                        'properties': {
                            'source': node_1['properties']['OLO'],
                            'sink': node_2['properties']['OLO'],
                            'population': exchange['properties']['population'],
                            'level': 'core',
                            'inner': exchange['properties']['inner'],
                            'outer': exchange['properties']['outer'],
                            'metro': exchange['properties']['metro'],
                            'tier_1': exchange['properties']['tier_1'],
                            'msan': exchange['properties']['msan'],
                        }
                    })

        if int(exchange['properties']['outer']) > 0:

            closest_nodes =  list(
                idx_all_core.nearest(
                    coords.bounds,
                    4, objects='raw')
                    )

            for node_1 in closest_nodes:

                coords_node_1 = shape(node_1['geometry'])

                output.append({
                    'type': exchange['type'],
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [
                            list(geom.coords)[0],
                            list(coords_node_1.coords)[0],
                        ]
                    },
                    'properties': {
                        'source': exchange['properties']['OLO'],
                        'sink': node_1['properties']['OLO'],
                        'population': exchange['properties']['population'],
                        'level': 'core',
                        'inner': exchange['properties']['inner'],
                        'outer': exchange['properties']['outer'],
                        'metro': exchange['properties']['metro'],
                        'tier_1': exchange['properties']['tier_1'],
                        'msan': exchange['properties']['msan'],
                    }
                })

        if int(exchange['properties']['metro']) > 0:

            closest_nodes =  list(
                idx_all_core.nearest(
                    geom.bounds,
                    3, objects='raw')
                    )

            for node_1 in closest_nodes:

                coords_node_1 = shape(node_1['geometry'])

                output.append({
                    'type': exchange['type'],
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [
                            list(geom.coords)[0],
                            list(coords_node_1.coords)[0]]
                    },
                    'properties': {
                        'source': exchange['properties']['OLO'],
                        'sink': node_1['properties']['OLO'],
                        'population': exchange['properties']['population'],
                        'level': 'metro',
                        'inner': exchange['properties']['inner'],
                        'outer': exchange['properties']['outer'],
                        'metro': exchange['properties']['metro'],
                        'tier_1': exchange['properties']['tier_1'],
                        'msan': exchange['properties']['msan'],
                    }
                })

        if int(exchange['properties']['tier_1']) > 0:

            closest_nodes =  list(
                idx_metro.nearest(
                    geom.bounds,
                    3, objects='raw')
                    )

            for node_1 in closest_nodes:

                coords_node_1 = shape(node_1['geometry'])

                output.append({
                    'type': exchange['type'],
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [
                            list(geom.coords)[0],
                            list(coords_node_1.coords)[0]]
                    },
                    'properties': {
                        'source': exchange['properties']['OLO'],
                        'sink': node_1['properties']['OLO'],
                        'population': exchange['properties']['population'],
                        'level': 'tier_1',
                        'inner': exchange['properties']['inner'],
                        'outer': exchange['properties']['outer'],
                        'metro': exchange['properties']['metro'],
                        'tier_1': exchange['properties']['tier_1'],
                        'msan': exchange['properties']['msan'],
                    }
                })

        if int(exchange['properties']['msan']) > 0:

            closest_nodes =  list(
                idx_tier_1.nearest(
                    geom.bounds,
                    3, objects='raw')
                    )

            for node in closest_nodes:

                coords_nearest = shape(node['geometry'])

                output.append({
                    'type': exchange['type'],
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [
                            list(coords_nearest.coords)[0],
                            list(geom.coords)[0]]
                    },
                    'properties': {
                        'source': exchange['properties']['OLO'],
                        'sink': node['properties']['OLO'],
                        'population': exchange['properties']['population'],
                        'level': 'msan',
                        'inner': exchange['properties']['inner'],
                        'outer': exchange['properties']['outer'],
                        'metro': exchange['properties']['metro'],
                        'tier_1': exchange['properties']['tier_1'],
                        'msan': exchange['properties']['msan'],
                    }
                })

    island_names = set()
    for exchange in islands_lut:
        island_names.add(exchange['island'])

    island_edges = []

    for island_name in list(island_names):
        node_lut = []
        for exchange in islands:
            if exchange['properties']['island'] == island_name:
                geom1 = shape(exchange['geometry'])

                closest_node =  list(
                    idx_tier_1.nearest(
                        geom1.bounds,
                        1, objects='raw')
                        )[0]

                geom2 = shape(closest_node['geometry'])

                line = LineString([geom1, geom2])

                node_lut.append({
                    'OLO_island': exchange['properties']['OLO'],
                    'OLO_island_geom': mapping(geom1),
                    'OLO_mainland': closest_node['properties']['OLO'],
                    'OLO_mainland_geom': mapping(geom2),
                    'line': mapping(line),
                    'length': line.length,
                    'population': exchange['properties']['OLO'],
                    'inner': exchange['properties']['inner'],
                    'outer': exchange['properties']['outer'],
                    'metro': exchange['properties']['metro'],
                    'tier_1': exchange['properties']['tier_1'],
                    'msan': exchange['properties']['msan'],
                })

        ranked = sorted(node_lut, reverse=False, key=lambda x: x['length'])[0]

        island_edges.append({
            'type': 'Feature',
            'geometry': ranked['line'],
            'properties': {
                'source': ranked['OLO_island'],
                'sink': ranked['OLO_mainland'],
                'population': ranked['population'],
                'level': 'island',
                'inner': ranked['inner'],
                'outer': ranked['outer'],
                'metro': ranked['metro'],
                'tier_1': ranked['tier_1'],
                'msan': ranked['msan'],
            }
        })

    return output + island_edges


def write_shapefile(data, directory, filename, crs):
    """
    Write geojson data to shapefile.

    """
    prop_schema = []
    for name, value in data[0]['properties'].items():
        fiona_prop_type = next((
            fiona_type for fiona_type, python_type in \
                fiona.FIELD_TYPES_MAP.items() if \
                python_type == type(value)), None
            )

        prop_schema.append((name, fiona_prop_type))

    sink_driver = 'ESRI Shapefile'
    sink_crs = {'init': crs}
    sink_schema = {
        'geometry': data[0]['geometry']['type'],
        'properties': OrderedDict(prop_schema)
    }

    if not os.path.exists(directory):
        os.makedirs(directory)

    with fiona.open(
        os.path.join(directory, filename), 'w',
        driver=sink_driver, crs=sink_crs, schema=sink_schema) as sink:
        for datum in data:
            sink.write(datum)


if __name__ == '__main__':

    path = os.path.join(BASE_PATH, 'telecoms_nodes.shp')
    exchanges = read_existing_nodes(path)#[:10]
    print('total number of exchanges: {}'.format(len(exchanges)))

    path = os.path.join(BASE_PATH, 'core_bt_21cn.csv')
    lookup = read_lookup(path)

    exchanges = determine_nodes(exchanges, lookup)

    crs = 'epsg:27700'
    write_shapefile(exchanges, DATA_INTERMEDIATE, 'nodes.shp', crs)

    path = os.path.join(DATA_INTERMEDIATE, 'islands', 'all_islands.csv')
    islands_lut = import_islands(path)

    exchanges, islands, island_edges = process_islands(exchanges, islands_lut)

    edges = connect(exchanges, islands, islands_lut)

    write_shapefile(edges + island_edges, DATA_INTERMEDIATE, 'edges.shp', crs)
