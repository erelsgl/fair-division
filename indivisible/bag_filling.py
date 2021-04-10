#!python3

"""
A utility class Bag for bag-filling --- a subroutine in 
    various algorithms for fair allocation of indivisible items.

Programmer: Erel Segal-Halevi
Since:  2021-04
"""

from fairpy import ValuationMatrix, Allocation
from typing import List
import numpy as np

import logging
logger = logging.getLogger(__name__)


#####################


class Bag:
	"""
	represents a bag for objects. 
	Different agents may have different valuations for the objects.
	>>> valuations = ValuationMatrix([[11,33],[44,22]])
	>>> thresholds = [30,30]
	>>> bag = Bag(valuations, thresholds)
	>>> print(bag)
	Bag objects: [], values: [0. 0.]
	>>> print(bag.willing_agent([0,1]))
	None
	>>> bag.append(0)
	>>> print(bag)
	Bag objects: [0], values: [11. 44.]
	>>> print(bag.willing_agent([0,1]))
	1
	>>> bag.append(1)
	>>> print(bag)
	Bag objects: [0, 1], values: [44. 66.]
	>>> print(bag.willing_agent([0,1]))
	0
	"""
	objects: List[int]
	valuations: ValuationMatrix
	map_agent_to_bag_value: List[float]

	def __init__(self, valuations:ValuationMatrix, thresholds:List[float]):
		"""
		Initialize an empty bag.
		:param valuations: a matrix representing additive valuations (a row for each agent, a column for each object).
		:param thresholds: determines, for each agent, the minimum value that should be in a bag before the agent accepts it.
		"""
		self.valuations = ValuationMatrix(valuations)
		self.thresholds = thresholds
		self.reset()

	def reset(self): 
		"""
		Empty the bag.
		"""
		self.objects = []
		self.map_agent_to_bag_value = np.zeros(self.valuations.num_of_agents)
		logger.info("Starting an empty bag. %d agents and %d objects.", self.valuations.num_of_agents, self.valuations.num_of_objects)

	def append(self, object:int):
		"""
		Append the given object to the bag, and update the agents' valuations accordingly.
		"""
		logger.info("   Appending object %s.", object)
		self.objects.append(object)
		for agent in self.valuations.agents():
			self.map_agent_to_bag_value[agent] += self.valuations[agent][object]
		logger.debug("      Bag values: %s.", self.map_agent_to_bag_value)

	def willing_agent(self, remaining_agents)->int:
		"""
		:return the index of an arbitrary agent, from the list of remaining agents, who is willing to accept the bag 
		 (i.e., the bag's value is above the agent's threshold).
		 If no remaining agent is willing to accept the bag, None is returned.
		"""
		for agent in remaining_agents:
			logger.debug("      Checking if agent %d is willing to take the bag", agent)
			if self.map_agent_to_bag_value[agent] >= self.thresholds[agent]:
				return agent
		return None


	def fill(self, remaining_objects, remaining_agents)->(int, list):
		"""
		Fill the bag with objects until at least one agent is willing to accept it.
		:return the willing agent, or None if the objects are insufficient.
		>>> bag = Bag(valuations=[[1,2,3,4,5,6],[6,5,4,3,2,1]], thresholds=[10,10])
		>>> remaining_objects = list(range(6))
		>>> remaining_agents = [0,1]
		>>> (willing_agent, allocated_objects) = bag.fill(remaining_objects, remaining_agents)
		>>> willing_agent
		1
		>>> allocated_objects
		[0, 1]
		>>> remaining_objects = list(set(remaining_objects) - set(allocated_objects))
		>>> bag = Bag(valuations=[[1,2,3,4,5,6],[6,5,4,3,2,1]], thresholds=[10,10])
		>>> bag.fill(remaining_objects, remaining_agents)
		(0, [2, 3, 4])
		>>> bag = Bag(valuations=[[20]], thresholds=[10])  # Edge case: single object
		>>> bag.fill(remaining_objects=[0], remaining_agents=[0])
		(0, [0])
		>>> bag = Bag(valuations=[[20,5]], thresholds=[10])  # Edge case: bag with an existing large object
		>>> bag.append(0)
		>>> bag.fill(remaining_objects=[1], remaining_agents=[0])
		(0, [0])
		"""
		if len(remaining_agents)==0:
			return (None, None)
		willing_agent = self.willing_agent(remaining_agents)
		if willing_agent is not None:
			return (willing_agent, self.objects)
		for object in remaining_objects:
			self.append(object)
			willing_agent = self.willing_agent(remaining_agents)
			if willing_agent is not None:
				return (willing_agent, self.objects)
		return (None, None)

	def __str__(self):
		return f"Bag objects: {self.objects}, values: {self.map_agent_to_bag_value}"


#####################


def one_directional_bag_filling(valuations:ValuationMatrix, thresholds:List[float]):
	"""
	The simplest bag-filling procedure: fills a bag in the given order of objects.
	
	:param valuations: a valuation matrix (a row for each agent, a column for each object).
	:param thresholds: determines, for each agent, the minimum value that should be in a bag before the agent accepts it.

	>>> one_directional_bag_filling(valuations=[[11,33],[44,22]], thresholds=[30,30])
	Agent #0 gets {1} with value 33.
	Agent #1 gets {0} with value 44.
	<BLANKLINE>
	>>> one_directional_bag_filling(valuations=[[11,33],[44,22]], thresholds=[10,10])
	Agent #0 gets {0} with value 11.
	Agent #1 gets {1} with value 22.
	<BLANKLINE>
	>>> one_directional_bag_filling(valuations=[[11,33],[44,22]], thresholds=[40,30])
	Agent #0 gets None with value 0.
	Agent #1 gets {0} with value 44.
	<BLANKLINE>
	"""
	valuations = ValuationMatrix(valuations)
	if len(thresholds) != valuations.num_of_agents:
		raise ValueError(f"Number of valuations {valuations.num_of_agents} differs from number of thresholds {len(thresholds)}")

	allocations = [None] * valuations.num_of_agents
	remaining_objects = list(valuations.objects())
	remaining_agents  = list(valuations.agents())
	bag = Bag(valuations, thresholds)
	while True:
		(willing_agent, allocated_objects) = bag.fill(remaining_objects, remaining_agents)
		if willing_agent is None: break
		allocations[willing_agent] = allocated_objects
		remaining_agents.remove(willing_agent)
		for o in allocated_objects: remaining_objects.remove(o)
		logger.info("Agent %d takes the bag with objects %s. Remaining agents: %s. Remaining objects: %s.", willing_agent, allocated_objects, remaining_agents, remaining_objects)
		bag.reset()

	map_agent_to_bundle_value = [valuations.agent_value_for_bundle(agent,allocations[agent]) for agent in valuations.agents()]
	return Allocation(valuations.agents(), allocations, map_agent_to_bundle_value)



if __name__ == '__main__':
	import sys
	logger.addHandler(logging.StreamHandler(sys.stdout))
	# logger.setLevel(logging.DEBUG)

	import doctest
	(failures, tests) = doctest.testmod(report=True)
	print("{} failures, {} tests".format(failures, tests))
