"""
Capacity estimation method.

Written by Ed Oughton

December 12th 2019

This method can be used for any spatially aggregated unit, such as
postcode sectors or local authority districts. First, a points in
polygon analysis needs to provide the total number of 4G or 5G sites
in an area, in order to then get the density of assets. This method
then allocates the estimated capacity to the area.

"""
import os
import sys
import configparser
import csv
from itertools import tee

from collections import OrderedDict

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(os.path.dirname(__file__), 'script_config.ini'))
BASE_PATH = CONFIG['file_locations']['base_path']

DATA_RAW = os.path.join(BASE_PATH, 'raw')
DATA_INTERMEDIATE = os.path.join(BASE_PATH, 'intermediate')


def load_capacity_lookup_table(path):
    """
    Load a lookup table created using pysim5G:
    https://github.com/edwardoughton/pysim5g

    """
    capacity_lookup_table = {}

    # for path in PATH_LIST:
    with open(path, 'r') as capacity_lookup_file:
        reader = csv.DictReader(capacity_lookup_file)
        for row in reader:
            if float(row["capacity_mbps_km2"]) <= 0:
                continue
            environment = row["environment"].lower()
            cell_type = row["ant_type"]
            frequency = str(int(float(row["frequency_GHz"]) * 1e3))
            bandwidth = str(row["bandwidth_MHz"])
            generation = str(row["generation"])
            density = float(row["sites_per_km2"])
            capacity = float(row["capacity_mbps_km2"])

            if (environment, cell_type, frequency, bandwidth, generation) \
                not in capacity_lookup_table:
                capacity_lookup_table[(
                    environment, cell_type, frequency, bandwidth, generation)
                    ] = []

            capacity_lookup_table[(
                environment, cell_type, frequency, bandwidth, generation
                )].append((
                    density, capacity
                ))

        for key, value_list in capacity_lookup_table.items():
            value_list.sort(key=lambda tup: tup[0])

    return capacity_lookup_table


def estimate_area_capacity(assets, area, clutter_environment,
    capacity_lookup_table, simulation_parameters):
    """
    Find the macrocellular Radio Access Network capacity given the
    area assets and deployed frequency bands.

    """
    capacity = 0

    for frequency in ['700', '800', '1800', '2600', '3500', '26000']:

        unique_sites = set()
        for asset in assets:
            for asset_frequency in asset['frequency']:
                if asset_frequency == frequency:
                    unique_sites.add(asset['site_ngr'])

        site_density = float(len(unique_sites)) / area

        bandwidth = find_frequency_bandwidth(frequency,
            simulation_parameters)
        if frequency == '700' or frequency == '3500' or frequency == '26000':
            generation = '5G'
        else:
            generation = '4G'

        if site_density > 0:
            tech_capacity = lookup_capacity(
                capacity_lookup_table,
                clutter_environment,
                'macro',
                str(frequency),
                str(bandwidth),
                generation,
                site_density,
                )
        else:
            tech_capacity = 0

        capacity += tech_capacity

    return capacity


def find_frequency_bandwidth(frequency, simulation_parameters):
    """
    Finds the correct bandwidth for a specific frequency from the
    simulation parameters.
    """
    simulation_parameter = 'channel_bandwidth_{}'.format(frequency)

    if simulation_parameter not in simulation_parameters.keys():
        KeyError('{} not specified in simulation_parameters'.format(frequency))

    bandwidth = simulation_parameters[simulation_parameter]

    return bandwidth


def pairwise(iterable):
    """
    Return iterable of 2-tuples in a sliding window.
    >>> list(pairwise([1,2,3,4]))
    [(1,2),(2,3),(3,4)]
    """
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def lookup_capacity(lookup_table, environment, cell_type, frequency, bandwidth,
    generation, site_density):
    """
    Use lookup table to find capacity by clutter environment geotype,
    frequency, bandwidth, technology generation and site density.

    """
    # print(lookup_table)
    if (environment, cell_type, frequency, bandwidth, generation) not in lookup_table:
        raise KeyError("Combination %s not found in lookup table",
                       (environment, cell_type, frequency, bandwidth, generation))

    density_capacities = lookup_table[
        (environment, cell_type, frequency, bandwidth, generation)
    ]

    lowest_density, lowest_capacity = density_capacities[0]
    if site_density < lowest_density:
        return 0

    for a, b in pairwise(density_capacities):

        lower_density, lower_capacity = a
        upper_density, upper_capacity = b

        if lower_density <= site_density and site_density < upper_density:

            result = interpolate(
                lower_density, lower_capacity,
                upper_density, upper_capacity,
                site_density
            )
            return result

    # If not caught between bounds return highest capacity
    highest_density, highest_capacity = density_capacities[-1]

    return highest_capacity


def interpolate(x0, y0, x1, y1, x):
    """
    Linear interpolation between two values.
    """
    y = (y0 * (x1 - x) + y1 * (x - x0)) / (x1 - x0)

    return y


if __name__ == '__main__':

    #define parameters
    PARAMETERS = {
        'channel_bandwidth_700': '10',
        'channel_bandwidth_800': '10',
        'channel_bandwidth_1800': '10',
        'channel_bandwidth_2600': '10',
        'channel_bandwidth_3500': '40',
        'channel_bandwidth_3700': '40',
        'channel_bandwidth_26000': '200',
        'macro_sectors': 3,
        'small-cell_sectors': 1,
        'mast_height': 30,
    }

    #define assets
    ASSETS = [
        {
            'site_ngr': 'A',
            'frequency': ['800', '2600'],
            'technology': '4G',
            'type': 'macrocell_site',
            'bandwidth': '2x10MHz',
            'build_date': 2018,
        },
        {
            'site_ngr': 'B',
            'frequency': ['800', '2600'],
            'technology': '4G',
            'type': 'macrocell_site',
            'bandwidth': '2x10MHz',
            'build_date': 2018,
        },
    ]

    path = os.path.join(DATA_RAW, 'capacity_lut_by_frequency_10.csv')
    capacity_lookup_table = load_capacity_lookup_table(path)

    area_capacity = estimate_area_capacity(ASSETS, 10, 'urban',
        capacity_lookup_table, PARAMETERS)

    print(area_capacity)
