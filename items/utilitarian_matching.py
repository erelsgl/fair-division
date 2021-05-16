#!python3

"""
SETTING: 
* There are n agents.
* There are k items; from each item, there may be several units.
* Each agent may have a different value for each item.

GOAL: Assign a single item-unit to each agent, such that the sum of values is maximum.

VARIANTS: allows to give priorities to agents, i.e., multiply their weights by a factor.

Author: Erel Segal-Halevi
Since : 2021-04
"""

import networkx
from typing import *
from collections import defaultdict
from dicttools import stringify
from fairpy.allocations import Allocation

import logging
logger = logging.getLogger(__name__)

AgentsDict = Dict[str, Dict[str, int]]

def instance_to_graph(agents: AgentsDict,  agent_weights: Dict[str, int]=None, item_capacities: Dict[str,int]=None)->networkx.Graph:
    """
    Converts agents' preferences to a bipartite graph (a networkx object).
    :param agents: maps each agent to a map from an item's name to its value for the agent.
    :param agent_weights [optional]: maps each agent to a weight. The values of each agent are multiplied by the agent's weight.
    :param item_capacities [optional]: maps each item to its number of units. Default is 1.

    >>> prefs = {"avi": {"x":5, "y": 4}, "beni": {"x":2, "y":3}}
    >>> graph = instance_to_graph(prefs) 
    >>> list(graph.edges.data())
    [('avi', 'x', {'weight': 5}), ('avi', 'y', {'weight': 4}), ('x', 'beni', {'weight': 2}), ('y', 'beni', {'weight': 3})]
    >>> graph = instance_to_graph(prefs, item_capacities={"x":1, "y":2}) 
    >>> list(graph.edges.data())
    [('avi', 'x', {'weight': 5}), ('avi', ('y', 0), {'weight': 4}), ('avi', ('y', 1), {'weight': 4}), ('x', 'beni', {'weight': 2}), (('y', 0), 'beni', {'weight': 3}), (('y', 1), 'beni', {'weight': 3})]
    >>> graph = instance_to_graph(prefs, agent_weights={"avi":1, "beni":100}) 
    >>> list(graph.edges.data())
    [('avi', 'x', {'weight': 5}), ('avi', 'y', {'weight': 4}), ('x', 'beni', {'weight': 200}), ('y', 'beni', {'weight': 300})]
    """
    graph = networkx.Graph()
    for agent,agentprefs in agents.items():
        for good,value in agentprefs.items():
            weight=value
            if agent_weights is not None:
                weight *= agent_weights.get(agent,1)
            num_of_units = 1 # default capacity
            if item_capacities is not None:
                num_of_units = item_capacities.get(good, 0)  # get the capacity from the map. If it is not in the map, the capacity is 0.
            if num_of_units==1:
                graph.add_edge(agent, good, weight=weight)
            else:
                for c in range(num_of_units):
                    graph.add_edge(agent, (good,c), weight=weight)
    return graph


def matching_to_allocation(matching: list, agent_names:list, agent_weights: Dict[str, int]=None)->Dict[str,str]:
    """
    Converts a one-to-many matching in a bipartite graph (output of networkx) to an allocation (given as a dict)
    :param matching: a list of pairs (agent,item).
    :param agent_weights [optional]: maps each agent to an integer priority. Used for sorting the agents in the list for each item.

    :return a dict, mapping an agent to its bundle.

    >>> matching = [("a", "xxx"), ("b", "yyy"), ("c", "yyy")]
    >>> map_agent_to_bundle = matching_to_allocation(matching, ["a","b","c"])
    >>> stringify(map_agent_to_bundle)
    "{a:['xxx'], b:['yyy'], c:['yyy']}"
    >>> matching = [("a", "xxx"), ("b", "yyy"), ("c", "yyy")]
    >>> agent_weights = {"a":1, "b":10, "c":100}
    >>> map_agent_to_bundle = matching_to_allocation(matching, ["a","b","c"], agent_weights=agent_weights)
    >>> stringify(map_agent_to_bundle)
    "{a:['xxx'], b:['yyy'], c:['yyy']}"
    """
    map_agent_to_matched_good = {}
    for edge in matching:
        if edge[0] in agent_names:  
            (agent,good)=edge
        elif edge[1] in agent_names:
            (good,agent)=edge
        else:
            raise ValueError(f"Cannot find an agent in {edge}")
        if isinstance(good, tuple):  # when there are several units of the same good...
            good = good[0]           # ... 0 is the good, 1 is the unit-number. 
        map_agent_to_matched_good[agent] = good
    map_agent_to_bundle = {agent:[good] for agent,good in map_agent_to_matched_good.items()}
    return map_agent_to_bundle
    



def utilitarian_matching(agents: AgentsDict, agent_weights: Dict[str, int]=None, item_capacities: Dict[str,int]=None, maxcardinality=True):
    """
    Finds a maximum-weight matching with the given preferences, agent_weights and capacities.
    :param agents: maps each agent to a map from an item's name to its value for the agent.
    :param agent_weights [optional]: maps each agent to an integer priority. The weights of each agent are multiplied by WEIGHT_BASE^priority.
    :param item_capacities [optional]: maps each item to its number of units. Default is 1.
    :param maxcardinality: True to require maximum weight subject to maximum cardinality. False to require only maximum weight.

    >>> prefs = {"avi": {"x":5, "y": 4}, "beni": {"x":2, "y":3}}
    >>> alloc = utilitarian_matching(prefs)
    >>> stringify(alloc.map_agent_to_bundle())
    "{avi:['x'], beni:['y']}"
    >>> stringify(alloc.map_item_to_agents())
    "{x:['avi'], y:['beni']}"
    >>> prefs = {"avi": {"x":5, "y": -2}, "beni": {"x":2, "y":-3}}
    >>> utilitarian_matching(prefs, maxcardinality=True)
    avi gets {x} with value 5.
    beni gets {y} with value -3.
    <BLANKLINE>
    >>> utilitarian_matching(prefs, maxcardinality=False)
    avi gets {x} with value 5.
    beni gets None with value 0.
    <BLANKLINE>
    >>> prefs = {"avi": {"x":5, "y": 4}, "beni": {"x":2, "y":3}, "gadi": {"x":3, "y":2}}
    >>> alloc = utilitarian_matching(prefs, item_capacities={"x":2, "y":2})
    >>> stringify(alloc.map_agent_to_bundle())
    "{avi:['x'], beni:['y'], gadi:['x']}"
    >>> stringify(alloc.map_item_to_agents())
    "{x:['avi', 'gadi'], y:['beni']}"
    >>> agent_weights = {"avi":1, "gadi":10, "beni":100}
    >>> stringify(alloc.map_item_to_agents(sortkey=lambda name: -agent_weights[name]))
    "{x:['gadi', 'avi'], y:['beni']}"
    """
    graph = instance_to_graph(agents, agent_weights=agent_weights, item_capacities=item_capacities)
    logger.info("Graph edges: %s", list(graph.edges.data()))
    matching = networkx.max_weight_matching(graph, maxcardinality=maxcardinality)
    logger.info("Matching: %s", matching)
    map_agent_to_bundle = matching_to_allocation(matching, agent_names=agents.keys(), agent_weights=agent_weights)
    return Allocation(agents, map_agent_to_bundle)


if __name__ == "__main__":
    # import sys
    # logger.addHandler(logging.StreamHandler(sys.stdout))
    # logger.setLevel(logging.INFO)

    import doctest
    (failures, tests) = doctest.testmod(report=True,optionflags=doctest.NORMALIZE_WHITESPACE)
    print("{} failures, {} tests".format(failures, tests))
