"""This module provides compositional component classes the ability to propogate
plant-wide design inputs throughout all of its subcomponents.

Since it becomes tedious to pass said plant-wide design inputs manually to each
subcomponent, this module creates a cache-like data structure that allows a
component and all of its subcomponents to access a set of shared inputs.

Example:
    from aguaclara.design.component import *
    
    class SubComponent(Component):
        def __init__(self, pi=PlantInput(),
                     h=3 * u.m):
            super().__init__(pi = pi)
            self.h = h

    class MainComponent(Component):
        def __init__(self, pi=PlantInput(),
                     l=2 * u.m,
                     sub=SubComponent()):
            super().__init__(pi = pi)
            self.l = l

            super().propogate_config([self.sub])
"""
from aguaclara.core.units import unit_registry as u

class PlantInput(object):
    """Represents the design inputs that are shared between all components
    of an AguaClara water treatment plant.
    
    Attributes:
        - ``configs ({string: PlantInput})``: A dictionary mapping the hexcode
          memory locations of component objects to their plant design inputs.

    Args:
        - ``q (float * u.L / u.s)``: Flow rate (recommended, defaults to 20 l/s)
        - ``temp (float * u.degC)``: Water temperature (recommended, defaults to
          20°C)
    """
    configs = {}

    def __init__(self, q=20 * u.L / u.s, temp=20 * u.degC):
        self.q = q
        self.temp = temp
        
class Component(object):
    """An abstract class that should be extended by other component classes.

    This class provides the ability to record and propogate a configuration of
    plant design variables for a component and all of its subcomponents.

    Args:
        - ``pi (PlantInput)``: The shared plant design inputs for a component
          object
    """                                                                                             
    # PlantInput implementation
    # def __init__(self, pi = PlantInput()):
    #     self.mem_loc = hex(id(self))

    #     if self.mem_loc not in PlantInput.configs:
    #         PlantInput.configs[self.mem_loc] = pi

    # Plant inputs as expert inputs implementation
    def __init__(self, q=20.0 * u.L/u.s, temp=20.0 * u.degC):
        self.mem_loc = hex(id(self))

        if self.mem_loc not in PlantInput.configs:
            PlantInput.configs[self.mem_loc] = PlantInput(q, temp)

    @property
    def q(self):
        """The flow rate. (L/s)"""
        return PlantInput.configs[self.mem_loc].q
    
    @property
    def temp(self):
        """The water temperature. (°C)"""
        return PlantInput.configs[self.mem_loc].temp

    def propogate_config(self, subcomponents):
        """Propogate the configuration of plant design inputs to all
        subcomponents.
        
        Args:
            - ``subcomponents ([Component])``: A list of subcomponents for the
              Component class.
        """
        for subcomp in subcomponents:
            sub_mem_loc = hex(id(subcomp))
            PlantInput.configs[sub_mem_loc] = \
                PlantInput.configs[self.mem_loc]


# # With PlantInput
# from aguaclara.design.component import *

# class SubComponent(Component):
#     def __init__(self, pi=PlantInput(),
#                     h=3 * u.m):
#         super().__init__(pi = pi)
#         self.h = h

# class MainComponent(Component):
#     def __init__(self, pi=PlantInput(),
#                     l=2 * u.m,
#                     sub=SubComponent()):
#         super().__init__(pi = pi)
#         self.l = l

#         super().propogate_config([self.sub])

# # Without PlantInput
# from aguaclara.design.component import *

# class SubComponent(Component):
#     def __init__(self, q=20.0 * u.L / u.s, temp=20.0 * u.degC,
#                     h=3 * u.m):
#         super().__init__(q = q, temp = temp)
#         self.h = h

# class MainComponent(Component):
#     def __init__(self, q=20.0 * u.L / u.s, temp=20.0 * u.degC,
#                     l=2 * u.m,
#                     sub=SubComponent()):
#         super().__init__(q = q, temp = temp)
#         self.l = l

#         super().propogate_config([self.sub])