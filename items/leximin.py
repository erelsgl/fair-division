#!python3

""" 
Find a fractionl allocation that maximizes the leximin vector.
Based on:

Stephen J. Willson
["Fair Division Using Linear Programming"](https://swillson.public.iastate.edu/FairDivisionUsingLPUnpublished6.pdf)
* Part 6, pages 20--27.

Programmer: Erel Segal-Halevi.
  I am grateful to Sylvain Bouveret for his help with the algorithm. All errors and bugs are my own.

See also: [max_welfare.py](max_welfare.py).

Since:  2021-05
"""

import numpy as np, cvxpy
from fairpy import valuations, Allocation, AllocationToFamilies, map_agent_to_family
from fairpy.solve import maximize
from typing import List

import logging
logger = logging.getLogger(__name__)


##### Utility functions for comparing leximin vectors

def is_leximin_better(x:list, y:list):
    """
    >>> is_leximin_better([6,2,4],[7,3,1])
    True
    >>> is_leximin_better([6,2,4],[3,3,3])
    False
    """
    return sorted(x) > sorted(y)


TOLERANCE_FACTOR=1.001  # for comparing floating-point numbers


#### Generic leximin solver:

def leximin_optimal_solution(variables, utilities, constraints) -> np.ndarray:
    """
    Find a leximin-optimal vector of utilities, subject to the given constraints.
    :param variables: an array of cvxpy variables, over which the optimization is done.
    :param utilities: a list of cvxpy expressions using these variables, representing the agents' utilities.
    :param constraints: a list of cvxpy constraints.
    :return an ndarray with the optimal values of the given variables.

    For usage examples and doctests, see the functions below: leximin_optimal_allocation, leximin_optimal_allocation_for_families.
    """
    leximin_optimal_solution.num_of_calls_to_solver = 0  # for performance analysis
    num_of_agents = len(utilities)

    # Initially all agents are free - no agent is saturated:
    free_agents = list(range(num_of_agents))
    map_saturated_agent_to_saturated_utility = num_of_agents * [None]
    order_constraints_for_saturated_agents = []

    while True:
        logger.info("Saturated utilities: %s.", map_saturated_agent_to_saturated_utility)
        min_utility_for_free_agents = cvxpy.Variable()
        order_constraints_for_free_agents = [
            utilities[i] >= min_utility_for_free_agents
            for i in free_agents
        ]
        max_min_utility_for_free_agents = maximize(min_utility_for_free_agents, constraints + order_constraints_for_saturated_agents + order_constraints_for_free_agents)
        leximin_optimal_solution.num_of_calls_to_solver += 1
        utilities_in_max_min_allocation = [utility.value for utility in utilities]
        logger.info("  max min value: %g, utility-profile: %s", max_min_utility_for_free_agents, utilities_in_max_min_allocation)

        for ifree in free_agents:  # Find whether i's utility can be improved
            if utilities_in_max_min_allocation[ifree] > TOLERANCE_FACTOR*max_min_utility_for_free_agents:
                logger.info("  Max utility of agent #%d is at least %g, so agent remains free.", ifree, utilities_in_max_min_allocation[ifree])
                continue
            new_order_constraints_for_free_agents = [
                utilities[i] >= max_min_utility_for_free_agents
                for i in free_agents if i!=ifree
            ]
            max_utility_for_ifree = maximize(utilities[ifree], constraints + order_constraints_for_saturated_agents + new_order_constraints_for_free_agents)
            leximin_optimal_solution.num_of_calls_to_solver += 1
            if max_utility_for_ifree > TOLERANCE_FACTOR*max_min_utility_for_free_agents:
                logger.info("  Max utility of agent #%d is %g, so agent remains free.", ifree, max_utility_for_ifree)
                continue
            logger.info("  Max utility of agent #%d is %g, so agent becomes saturated.", ifree, max_utility_for_ifree)
            map_saturated_agent_to_saturated_utility[ifree] = max_min_utility_for_free_agents
            order_constraints_for_saturated_agents.append(utilities[ifree] >= max_min_utility_for_free_agents)

        new_free_agents = [i for i in free_agents if map_saturated_agent_to_saturated_utility[i] is None]
        if len(new_free_agents)==len(free_agents):
            raise ValueError("No new saturated agents - this contradicts Willson's theorem!")
        elif len(new_free_agents)==0:
            logger.info("All agents are saturated -- utility profile is %s.", map_saturated_agent_to_saturated_utility)
            logger.info("%d calls to solver.", leximin_optimal_solution.num_of_calls_to_solver)
            return variables.value
        else:
            free_agents = new_free_agents
            continue




##### Find a leximin-optimal allocation for individual agents

def leximin_optimal_allocation(agents) -> Allocation:
    """
    Find the leximin-optimal (aka Egalitarian) allocation.
    :param v: a matrix v in which each row represents an agent, each column represents an object, and v[i][j] is the value of agent i to object j.

    :return allocation_matrix:  a matrix alloc of a similar shape in which alloc[i][j] is the fraction allocated to agent i from object j.
    The allocation should maximize the leximin vector of utilities.
    >>> logger.setLevel(logging.WARNING)
    >>> a = leximin_optimal_allocation([[5,0],[3,3]])
    >>> a
    Agent #0 gets { 75.0% of 0} with value 3.75.
    Agent #1 gets { 25.0% of 0, 100.0% of 1} with value 3.75.
    <BLANKLINE>
    >>> a.matrix
    [[0.75 0.  ]
     [0.25 1.  ]]
    >>> a.utility_profile()
    array([3.75, 3.75])
    >>> v = [[3,0],[5,5]]
    >>> print(leximin_optimal_allocation(v).round(3).utility_profile())
    [3. 5.]
    >>> v = [[5,5],[3,0]]
    >>> print(leximin_optimal_allocation(v).round(3).utility_profile())
    [5. 3.]
    >>> v = [[3,0,0],[0,4,0],[5,5,5]]
    >>> print(leximin_optimal_allocation(v).round(3).utility_profile())
    [3. 4. 5.]
    >>> v = [[4,0,0],[0,3,0],[5,5,10],[5,5,10]]
    >>> print(leximin_optimal_allocation(v).round(3).utility_profile())
    [4. 3. 5. 5.]
    >>> v = [[3,0,0],[0,3,0],[5,5,10],[5,5,10]]
    >>> a = leximin_optimal_allocation(v)
    >>> print(a.round(3).utility_profile())
    [3. 3. 5. 5.]
    >>> logger.setLevel(logging.WARNING)
    """
    v = valuations.matrix_from(agents)

    alloc = cvxpy.Variable((v.num_of_agents, v.num_of_objects))
    feasibility_constraints = [
        sum([alloc[i][o] for i in v.agents()])==1
        for o in v.objects()
    ]
    positivity_constraints = [
        alloc[i][o] >= 0 for i in v.agents()
        for o in v.objects()
    ]
    utilities = [sum([alloc[i][o]*v[i][o] for o in v.objects()]) for i in v.agents()]

    allocation_matrix = leximin_optimal_solution(alloc, utilities, feasibility_constraints+positivity_constraints)
    return Allocation(v, allocation_matrix)


##### leximin for families


def leximin_optimal_allocation_for_families(agents, families:list) -> AllocationToFamilies:
    """
    Find the leximin-optimal (aka Egalitarian) allocation among families.
    :param agents: a matrix v in which each row represents an agent, each column represents an object, and v[i][j] is the value of agent i to object j.
    :param families: a list of lists. Each list represents a family and contains the indices of the agents in the family.

    :return allocation_matrix:  a matrix alloc of a similar shape in which alloc[i][j] is the fraction allocated to agent i from object j.
    The allocation should maximize the leximin vector of utilities.
    >>> families = [ [0], [1] ]  # two singleton families
    >>> v = [[5,0],[3,3]]
    >>> print(leximin_optimal_allocation_for_families(v,families).round(3).utility_profile())
    [3.75 3.75]
    >>> v = [[3,0],[5,5]]
    >>> print(leximin_optimal_allocation_for_families(v,families).round(3).utility_profile())
    [3. 5.]
    >>> families = [ [0], [1], [2] ]  # three singleton families
    >>> v = [[3,0,0],[0,4,0],[5,5,5]]
    >>> print(leximin_optimal_allocation_for_families(v,families).round(3).utility_profile())
    [3. 4. 5.]
    >>> families = [ [0, 1], [2] ]  
    >>> print(leximin_optimal_allocation_for_families(v,families).round(3).utility_profile())
    [3. 4. 5.]
    >>> families = [ [0], [1,2] ]  
    >>> print(leximin_optimal_allocation_for_families(v,families).round(3).utility_profile())
    [ 3.  4. 10.]
    >>> families = [ [1], [0,2] ]  
    >>> print(leximin_optimal_allocation_for_families(v,families).round(3).utility_profile())
    [ 3.  4. 10.]
    """
    v = valuations.matrix_from(agents)
    num_of_families = len(families)
    agent_to_family = map_agent_to_family(families, v.num_of_agents)
    logger.info("map_agent_to_family = %s",agent_to_family)

    alloc = cvxpy.Variable((num_of_families, v.num_of_objects))
    feasibility_constraints = [
        sum([alloc[f][o] for f in range(num_of_families)])==1
        for o in v.objects()
    ]
    positivity_constraints = [
        alloc[f][o] >= 0 for f in range(num_of_families)
        for o in v.objects()
    ]
    utilities = [sum([alloc[agent_to_family[i]][o]*v[i][o] for o in v.objects()]) for i in v.agents()]
    allocation_matrix = leximin_optimal_solution(alloc, utilities, feasibility_constraints+positivity_constraints)
    return AllocationToFamilies(v, allocation_matrix, families)



if __name__ == '__main__':
    import doctest
    (failures, tests) = doctest.testmod(report=True)
    print("{} failures, {} tests".format(failures, tests))
