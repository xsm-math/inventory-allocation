"""Validated network configuration and observable physical state."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import numpy as np

@dataclass
class Network:
    raw: dict
    def __post_init__(self):
        d = self.raw
        self.W, self.C, self.P = len(d['warehouses']), len(d['channels']), len(d['products'])
        if not self.W or not self.C or not self.P or d['modes'] != ['ground', 'express']:
            raise ValueError('Nonempty dimensions and ground/express modes required')
        shapes = {'unit_cost': (self.P,), 'volume': (self.P,), 'price': (self.C,self.P),
                  'shortage_penalty': (self.C,self.P), 'mean_demand': (self.C,self.P),
                  'warehouse_initial': (self.W,self.P), 'channel_initial': (self.C,self.P),
                  'warehouse_handling': (self.W,), 'supplier_capacity': (self.P,),
                  'ground_lead': (self.W,self.C), 'ground_cost': (self.W,self.C),
                  'lane_capacity': (2,), 'dispatch_fixed_cost': (2,),
                  'warehouse_holding': (self.P,), 'channel_holding': (self.P,)}
        integers = {'volume','warehouse_initial','channel_initial','warehouse_handling','supplier_capacity','ground_lead','lane_capacity'}
        for name, shape in shapes.items():
            a = np.asarray(d[name],dtype=float)
            if a.shape != shape or not np.isfinite(a).all() or (a < 0).any():
                raise ValueError(f'Invalid {name}: expected finite nonnegative {shape}')
            if name in integers and (a % 1).any():
                raise ValueError(f'{name} must contain integers')
            setattr(self, name, a.astype(int) if name in integers else a)
        for name in ['procurement_budget','supplier_lead','express_cost_multiplier','salvage_fraction','service_target','service_slack_penalty']:
            v = d[name]
            if isinstance(v,bool) or not np.isfinite(v) or v < 0:
                raise ValueError(f'Invalid {name}')
            setattr(self,name,v)
        if (self.unit_cost <= 0).any() or (self.volume <= 0).any() or self.supplier_lead < 1 or int(self.supplier_lead) != self.supplier_lead or (self.ground_lead < 1).any():
            raise ValueError('Positive costs, volumes and integral positive lead times required')
        if not 0 <= self.salvage_fraction <= 1 or not 0 <= self.service_target <= 1:
            raise ValueError('Fractions must lie in [0,1]')
        self.supplier_lead = int(self.supplier_lead)
        self.lead = np.stack([self.ground_lead,np.zeros_like(self.ground_lead)],axis=-1)
        self.freight = np.stack([self.ground_cost,self.ground_cost*self.express_cost_multiplier],axis=-1)

    @classmethod
    def load(cls, path=None):
        path = path or Path(__file__).resolve().parents[1]/'configs/network.json'
        return cls(json.loads(Path(path).read_text()))

@dataclass
class State:
    warehouse: np.ndarray
    channel: np.ndarray
    inbound: dict = field(default_factory=dict)  # absolute arrival day -> warehouse/product
    outbound: dict = field(default_factory=dict) # absolute arrival day -> channel/product

    @classmethod
    def initial(cls, net):
        return cls(net.warehouse_initial.copy(), net.channel_initial.copy())

    def receive(self, day):
        self.warehouse += self.inbound.pop(day,np.zeros_like(self.warehouse))
        self.channel += self.outbound.pop(day,np.zeros_like(self.channel))

    def total_by_product(self):
        return (self.warehouse.sum(0)+self.channel.sum(0)
                +sum((a.sum(0) for a in self.inbound.values()),np.zeros(self.warehouse.shape[1],int))
                +sum((a.sum(0) for a in self.outbound.values()),np.zeros(self.channel.shape[1],int)))

@dataclass
class Action:
    orders: np.ndarray
    shipments: np.ndarray  # warehouse, channel, mode, product
    diagnostics: dict = field(default_factory=dict)

    @classmethod
    def zero(cls, net):
        return cls(np.zeros((net.W,net.P),int),np.zeros((net.W,net.C,2,net.P),int))


def validate_action(net, state, action, supply_factor=1.):
    for arr, shape in [(action.orders,(net.W,net.P)),(action.shipments,(net.W,net.C,2,net.P))]:
        if arr.shape != shape or not np.isfinite(arr).all() or (arr < 0).any() or (arr % 1).any():
            raise ValueError('Invalid action shape, sign or integrality')
    if (action.shipments.sum((1,2)) > state.warehouse).any():
        raise ValueError('Shipments exceed available warehouse stock')
    if (action.orders.sum(0) > np.floor(net.supplier_capacity*supply_factor)).any():
        raise ValueError('Supplier capacity exceeded')
    if (action.orders*net.unit_cost).sum() > net.procurement_budget*supply_factor+1e-6:
        raise ValueError('Procurement budget exceeded')
    volume = (action.shipments*net.volume).sum(-1)
    if (volume > net.lane_capacity[None,None,:]).any():
        raise ValueError('Lane capacity exceeded')
    if (volume.sum((1,2)) > net.warehouse_handling).any():
        raise ValueError('Warehouse throughput exceeded')
