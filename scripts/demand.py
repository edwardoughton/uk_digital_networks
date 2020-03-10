"""
Data demand estimation calculations

Written by Ed Oughton
December 12th 2019

This method can be applied per asset area,
using the gross population served by the
asset.

"""
def calculate_user_demand(parameters):
    """
    Calculate Mb/second from GB/month supplied by throughput scenario.
    E.g.
        2 GB per month
            * 1024 to find MB
            * 8 to covert bytes to bits
            * busy_hour_traffic = daily traffic taking place in the busy hour
            * 1/30 assuming 30 days per month
            * 1/3600 converting hours to seconds,
        = ~0.01 Mbps required per user

    """
    busy_hour_traffic = parameters['busy_hour_traffic_percentage'] / 100

    monthly_data = parameters['monthly_data_consumption_GB']

    user_demand = monthly_data * 1024 * 8 * busy_hour_traffic / 30 / 3600

    return user_demand


def total_demand(user_demand, population, area, parameters):
    """
    Estimate total demand based on:
        - population (raw number)
        - smartphone penetration (percentage)
        - market share (percentage)
        - user demand (Mbps)
        - area (km^2)

    E.g.::
        100 population
            * (80% / 100) penetration
            * (25% / 100) market share
        = 20 users
        20 users
            * 0.01 Mbps user demand
        = 0.2 total user throughput
        0.2 Mbps total user throughput during the busy hour
            / 1 km² area
        = 0.2 Mbps/km² area demand

    """
    penetration = parameters['penetration_percentage']

    market_share = parameters['market_share_percentage']

    users = population * (penetration / 100) * market_share

    user_throughput = users * user_demand

    demand_per_kmsq = user_throughput / area

    return demand_per_kmsq


if __name__ == "__main__":

    #define parameters
    PARAMETERS = {
        'monthly_data_consumption_GB': 3,
        'busy_hour_traffic_percentage': 20,
        'penetration_percentage': 80,
        'market_share_percentage': 25,

    }

    user_demand = calculate_user_demand(PARAMETERS)

    demand_km2 = total_demand(user_demand, 1000, 10, PARAMETERS)

    print(demand_km2)
