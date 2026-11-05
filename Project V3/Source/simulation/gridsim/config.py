from simulation.TL_Senior_Simulation_V4 import VOLTAGE_MIN_PU, VOLTAGE_MAX_PU, LINE_LOADING_LIMIT
LIMITS = {'voltage_min_pu': VOLTAGE_MIN_PU, 'voltage_max_pu': VOLTAGE_MAX_PU, 'loading_percent': LINE_LOADING_LIMIT}
# V4 demonstration assumptions, not measured Houston equipment data.
LINE_PARAMETERS = {'r_ohm_per_km': .05, 'x_ohm_per_km': .40, 'c_nf_per_km': 0, 'max_i_ka': 1.0}
ROUTING_FACTOR = 1.2  # Study assumption, not a surveyed route.
# Explicit synthetic interface transformer, not a utility equipment specification.
TRANSFORMER_PARAMETERS = {'sn_mva': 600, 'vn_hv_kv': 345, 'vn_lv_kv': 138,
                          'vk_percent': 12, 'vkr_percent': .3, 'pfe_kw': 0, 'i0_percent': 0, 'shift_degree': 0}
