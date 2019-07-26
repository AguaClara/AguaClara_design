from aguaclara.core.units import unit_registry as u
from aguaclara.core import physchem as pc
from aguaclara.core import head_loss as hl
import aguaclara.core.constants as con
import aguaclara.core.materials as mats
import aguaclara.core.utility as ut
from aguaclara.design.component import Component

import pandas as pd
import numpy as np
import os.path
from abc import ABC, abstractmethod

_dir_path = os.path.dirname(__file__)
_pipe_database_path = os.path.join(_dir_path, 'data/pipe_database.csv')
with open(_pipe_database_path) as pipe_database_file:
    _pipe_database = pd.read_csv(pipe_database_file)

_fitting_database_path = \
    os.path.join(_dir_path, 'data/fitting_database.csv')
with open(_fitting_database_path) as _fitting_database_file:
    _fitting_database = pd.read_csv(_fitting_database_file)

# TODO: Once we support a Pint version that supports use with Pandas DataFrame's
# (>=0.10.0), we can assign units to DataFrame's rather than converting them to
# NumPy arrays.
_available_sizes_raw = _pipe_database.query('Used==1')['NDinch']
AVAILABLE_SIZES = np.array(_available_sizes_raw) * u.inch

_available_ids_sch40_raw = _pipe_database.query('Used==1')['ID_SCH40']
AVAILABLE_IDS_SCH40 = np.array(_available_ids_sch40_raw) * u.inch


_available_fitting_sizes_raw = _fitting_database.query('Used==1')['size']
AVAILABLE_FITTING_SIZES = np.array(_available_fitting_sizes_raw) * u.inch

_available_fitting_ids_raw = _fitting_database.query('Used==1')['id_inch']
AVAILABLE_FITTING_IDS = np.array(_available_fitting_ids_raw)* u.inch


class PipelineComponent(Component, ABC):

    def __init__(self, **kwargs):
        if all (key in kwargs for key in ('size', 'id')):
            raise AttributeError(
                'A PipelineComponent must be instantiated with either the size '
                'or inner diameter, but not both.'
            )

        self.size = 0.5 * u.inch
        self.nu = pc.viscosity_kinematic(20 * u.degC)
        self.next = None
        self.k_minor = 0

        super().__init__(**kwargs)

        self._rep_ok()

        self.size = self.get_available_size(self.size)

    def get_available_size(self, size):
        """Return the next larger size which is available."""
        return ut.ceil_nearest(size, AVAILABLE_SIZES)

    @abstractmethod
    def headloss(self):
        pass

    @property
    def headloss_pipeline(self):
        if self.next is None:
            return self.headloss
        else:
            return self.headloss + self.next.headloss_pipeline
    
    def set_next_components_q(self):
        if self.next is not None:
            self.next.q = self.q
            self.next.set_next_components_q()

    def flow_pipeline(self, target_headloss):
        """
        This function takes a single pipeline with multiple sections, each potentially with different diameters,
        lengths and minor loss coefficients and determines the flow rate for a given headloss.
        """
        if type(self) is Pipe:
            flow = pc.flow_pipe(self.id, 
                    target_headloss, 
                    self.length, 
                    self.nu,
                    self.pipe_rough, 
                    self.k_minor)
        else:
            try:
                flow = pc.flow_pipe(
                    self.next.id,
                    target_headloss,
                    self.next.length,
                    self.next.nu,
                    self.next.pipe_rough,
                    self.next.k_minor)
            except AttributeError:
                raise AttributeError('Neither of the first two components in'
                    'this pipeline are Pipe objects.')
        err = 1.0
        headloss = self.headloss_pipeline
        
        while abs(err) > 0.01 :
            err = (target_headloss - headloss) / (target_headloss + headloss)
            flow = flow + err * flow
            self.q = flow
            self.set_next_components_q()
            headloss = self.headloss_pipeline
        return flow.to(u.L / u.s)
    
    @abstractmethod
    def format_print(self):
        pass

    def pprint(self):
        if self.next is None:
            return self.format_print()
        else:
            return self.format_print() + '\n' + self.next.pprint()
 
    def __str__(self):
        return self.pprint()
        
    def __repr__(self):
        return self.__str__()

    def _rep_ok(self):
        if self.next is not None:
            if type(self) is Pipe and type(self.next) not in [Elbow, Tee]:
                raise TypeError('Pipes must be connected with fittings.')
            elif type(self) in [Elbow] and type(self.next) not in [Pipe]:
                raise TypeError('Fittings must be followed by pipes.')
            
        
class Pipe(PipelineComponent):
    AVAILABLE_SPECS = ['sdr26', 'sdr41', 'sch40']

    def __init__(self, **kwargs):
        self.id = 0.476 * u.inch
        self.spec = 'sdr41'
        self.length = 1 * u.m
        self.pipe_rough = mats.PVC_PIPE_ROUGH

        super().__init__(**kwargs)

        if self.spec not in self.AVAILABLE_SPECS:
            raise AttributeError('spec must be one of:', self.AVAILABLE_SPECS)
        if 'size' in kwargs:
            self.id = self._get_id(self.size, self.spec)
        elif 'id' in kwargs:
            self.size = self._get_size(self.id, self.spec)

        if self.next is not None and self.size != self.next.size:
            raise ValueError('size of the next pipeline component must be the '
            'same size as the current pipeline component')
            
    @property
    def od(self):
        """The outer diameter of the pipe"""
        index = (np.abs(np.array(_pipe_database['NDinch']) - self.size.magnitude)).argmin()
        return _pipe_database.iloc[index, 1] * u.inch

    def _get_size(self, id_, spec):
        """Get the size of """
        if spec[:3] == 'sdr':
            return self._get_size_sdr(id_, int(spec[3:]))
        elif spec == 'sch40':
            return self._get_size_sch40(id_)

    def _get_id(self, size, spec):
        if spec[:3] == 'sdr':
            return self._get_id_sdr(size, int(spec[3:]))
        elif spec == 'sch40':
            return self._get_id_sch40(size)

    def _get_id_sdr(self, size, sdr):
        self.size = super().get_available_size(size)
        return self.size * (sdr - 2) / sdr

    def _get_id_sch40(self, size):
        self.size = super().get_available_size(size)
        myindex = (np.abs(AVAILABLE_SIZES - self.size)).argmin()
        return AVAILABLE_IDS_SCH40[myindex]

    def _get_size_sdr(self, id_, sdr):
        nd = super().get_available_size((id_ * sdr) / (sdr - 2))
        self.id = self._get_id_sdr(nd, sdr)
        return nd

    def _get_size_sch40(self, id_):
        myindex = (np.abs(AVAILABLE_IDS_SCH40 - id_)).argmin()
        self.id = AVAILABLE_IDS_SCH40[myindex]  
        return AVAILABLE_SIZES[myindex]

    def ID_SDR_all_available(self, SDR):
        """Return an array of inner diameters with a given SDR.

        IDs available are those commonly used based on the 'Used' column
        in the pipedb.
        """
        ID = []
        for i in range(len(AVAILABLE_SIZES)):
            ID.append(self._get_id_sdr(AVAILABLE_SIZES[i], SDR).magnitude)
        return ID * u.inch
    
    @property
    def headloss(self):
        """Return the total head loss from major and minor losses in a pipe."""
        return pc.headloss_fric(
                self.q, self.id, self.length, self.nu, self.pipe_rough
            )

    def format_print(self):
        return 'Pipe: (OD: {}, Size: {}, ID: {}, Length: {}, Spec: {})'.format(
            self.od, self.size, self.id, self.length, self.spec)
   
        
class Elbow(PipelineComponent):

    AVAILABLE_ANGLES = [90 * u.deg, 45 * u.deg]

    def __init__(self, **kwargs):
        self.angle = 90 * u.deg
        self.id = 0.848 * u.inch

        super().__init__(**kwargs)

        if self.angle == 45 * u.deg:
            self.k_minor = hl.EL45_K_MINOR
        elif self.angle == 90 * u.deg:
            self.k_minor = hl.EL90_K_MINOR
        else:
            raise ValueError('angle must be in ', self.AVAILABLE_ANGLES)

        if 'size' in kwargs:
            self.id = self._get_id(self.size)
        elif 'id' in kwargs:
            self.size = self._get_size(self.id)

        if self.next is not None and self.size != self.next.size:
            raise ValueError('The next component doesn\'t have the same size.')


    def _get_size(self, id_):
        """Get the size of """
        myindex = (np.abs(AVAILABLE_FITTING_IDS - id_)).argmin()
        self.id = AVAILABLE_FITTING_IDS[myindex]
        return AVAILABLE_FITTING_SIZES[myindex]

    def _get_id(self, size):
        myindex = (np.abs(AVAILABLE_FITTING_SIZES - size)).argmin()
        self.size = AVAILABLE_FITTING_SIZES[myindex]
        return AVAILABLE_FITTING_IDS[myindex]

    @property
    def headloss(self):
        return pc.elbow_minor_loss(self.q, self.id, self.k_minor).to(u.m)

    def format_print(self):
        return 'Elbow: (Size: {}, ID: {}, Angle: {})'.format(
            self.size, self.id, self.angle)

class Tee(PipelineComponent):

    AVAILABLE_PATHS = ['branch', 'run', 'stopper']
    
    def __init__(self, **kwargs):
        
        self.left = None
        self.left_type = 'branch'
        self.left_k_minor = None

        self.right = None
        self.right_type = 'stopper'
        self.right_k_minor = None
        
        self.id = 0.848 * u.inch

        super().__init__(**kwargs)
        
        if self.left_type == 'branch':
            self.left_k_minor = hl.TEE_FLOW_BR_K_MINOR
        elif self.left_type == 'run':
            self.left_k_minor = hl.TEE_FLOW_RUN_K_MINOR
        elif self.left_type == 'stopper':
            self.left_k_minor = None

        if self.right_type == 'branch':
            self.right_k_minor = hl.TEE_FLOW_BR_K_MINOR
        elif self.right_type == 'run':
            self.right_k_minor = hl.TEE_FLOW_RUN_K_MINOR
        elif self.right_type == 'stopper':
            self.right_k_minor = None
        
        if self.left_type == 'stopper':
            self.next = self.right
            self.next_type = self.right_type
        else:
            self.next = self.left
            self.next_type = self.left_type

        if 'size' in kwargs:
            self.id = self._get_id(self.size)
        elif 'id' in kwargs:
            self.size = self._get_size(self.id)
        
        self._rep_ok()

    @property
    def _headloss_left(self):
        return pc.elbow_minor_loss(self.q, self.id, self.left_k_minor).to(u.m)

    @property
    def _headloss_right(self):
        return pc.elbow_minor_loss(self.q, self.id, self.right_k_minor).to(u.m)

    @property
    def headloss(self):
        if self.left_type =='stopper':
            return self._headloss_right
        else:
            return self._headloss_left 

    def _get_size(self, id_):
        """Get the size of """
        myindex = (np.abs(AVAILABLE_FITTING_IDS - id_)).argmin()
        self.id = AVAILABLE_FITTING_IDS[myindex]
        return AVAILABLE_FITTING_SIZES[myindex]

    def _get_id(self, size):
        myindex = (np.abs(AVAILABLE_FITTING_SIZES - size)).argmin()
        self.size = AVAILABLE_FITTING_SIZES[myindex]        
        return AVAILABLE_FITTING_IDS[myindex]

    def format_print(self):
        return 'Tee: (Size: {}, ID: {}, Next Path Type: {})'.format(
            self.size, self.id, self.next_type)
    
    def _rep_ok(self):
        if [self.left_type, self.right_type].count('stopper') != 1:
            raise ValueError('All tees must have one stopper.')
            
        if self.left_type not in self.AVAILABLE_PATHS:
            raise ValueError(
                'type of branch for left outlet must be in ', 
                self.AVAILABLE_PATHS)
        
        if self.right_type not in self.AVAILABLE_PATHS:
            raise ValueError(
                'type of branch for right outlet must be in ', 
                self.AVAILABLE_PATHS)

        if self.next is not None and self.size != self.next.size:
            raise ValueError('The next component doesn\'t have the same size.')
        
        if self.next is not None and type(self.next) in [Elbow, Tee]:
             raise ValueError('Tees cannot be followed by other fittings.')