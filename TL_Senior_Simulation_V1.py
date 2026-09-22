import pandapower as pp
import pandapower.auxiliary
import numpy as np
import matplotlib.pyplot as plt


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_float(prompt, default):
    """
    Lets the user press Enter to accept a default value.
    """
    user_input = input(f"{prompt} [default = {default}]: ").strip()

    if user_input == "":
        return float(default)

    return float(user_input)


def calculate_q_mvar(p_mw, power_factor):
    """
    Converts real power and power factor into reactive power.
    """
    angle = np.arccos(power_factor)

    return p_mw * np.tan(angle)


def build_and_run_network(
    grid_voltage_kv,
    dc1_mw,
    dc1_q_mvar,
    dc2_mw,
    dc2_q_mvar,
    line_length_km,
    r_ohm_per_km,
    x_ohm_per_km,
    max_i_ka
):
    """
    Creates and solves a simple pandapower network.

                    Utility Grid
                         |
                    Source Bus
                     /      \
                  Line 1    Line 2
                    |         |
                 DC1 Bus   DC2 Bus
                    |         |
                   DC1       DC2
    """

    net = pp.create_empty_network()

    # --------------------------------------------------------
    # BUSES
    # --------------------------------------------------------

    source_bus = pp.create_bus(
        net,
        vn_kv=grid_voltage_kv,
        name="Grid Source"
    )

    dc1_bus = pp.create_bus(
        net,
        vn_kv=grid_voltage_kv,
        name="Data Center 1 Bus"
    )

    dc2_bus = pp.create_bus(
        net,
        vn_kv=grid_voltage_kv,
        name="Data Center 2 Bus"
    )

    # --------------------------------------------------------
    # GRID SOURCE
    # --------------------------------------------------------

    pp.create_ext_grid(
        net,
        bus=source_bus,
        vm_pu=1.0,
        name="Utility Grid"
    )

    # --------------------------------------------------------
    # TRANSMISSION LINES
    # --------------------------------------------------------

    pp.create_line_from_parameters(
        net,
        from_bus=source_bus,
        to_bus=dc1_bus,
        length_km=line_length_km,
        r_ohm_per_km=r_ohm_per_km,
        x_ohm_per_km=x_ohm_per_km,
        c_nf_per_km=0,
        max_i_ka=max_i_ka,
        name="Line to Data Center 1"
    )

    pp.create_line_from_parameters(
        net,
        from_bus=source_bus,
        to_bus=dc2_bus,
        length_km=line_length_km,
        r_ohm_per_km=r_ohm_per_km,
        x_ohm_per_km=x_ohm_per_km,
        c_nf_per_km=0,
        max_i_ka=max_i_ka,
        name="Line to Data Center 2"
    )

    # --------------------------------------------------------
    # DATA CENTER LOADS
    # --------------------------------------------------------

    pp.create_load(
        net,
        bus=dc1_bus,
        p_mw=dc1_mw,
        q_mvar=dc1_q_mvar,
        name="Data Center 1"
    )

    pp.create_load(
        net,
        bus=dc2_bus,
        p_mw=dc2_mw,
        q_mvar=dc2_q_mvar,
        name="Data Center 2"
    )

    # --------------------------------------------------------
    # RUN AC POWER FLOW
    # --------------------------------------------------------

    try:
        pp.runpp(
            net,
            algorithm="nr",
            max_iteration=30,
            tolerance_mva=1e-6
        )

        return net

    except pandapower.auxiliary.LoadflowNotConverged:
        return None


# ============================================================
# TITLE
# ============================================================

print("\n")
print("=" * 62)
print("      TEXAS DATA CENTER GRID IMPACT ")
print("=" * 62)

print("\nThis model uses pandapower to perform an AC power-flow")
print("simulation for two data centers connected to a grid source.")

print("\nPress Enter to use the suggested default values.")


# ============================================================
# USER INPUTS
# ============================================================

print("\n" + "=" * 62)
print("GRID SETTINGS")
print("=" * 62)

grid_voltage_kv = get_float(
    "Grid voltage (kV)",
    138
)

line_length_km = get_float(
    "Transmission line length to each data center (km)",
    10
)

line_r = get_float(
    "Line resistance (ohm/km)",
    0.05
)

line_x = get_float(
    "Line reactance (ohm/km)",
    0.40
)

max_i_ka = get_float(
    "Line current rating (kA)",
    1.0
)


print("\n" + "=" * 62)
print("DATA CENTER 1")
print("=" * 62)

dc1_mw = get_float(
    "Real power demand (MW)",
    100
)

dc1_pf = get_float(
    "Power factor",
    0.95
)


print("\n" + "=" * 62)
print("DATA CENTER 2")
print("=" * 62)

dc2_mw = get_float(
    "Real power demand (MW)",
    150
)

dc2_pf = get_float(
    "Power factor",
    0.95
)


# ============================================================
# REACTIVE POWER CALCULATIONS
# ============================================================

dc1_q_mvar = calculate_q_mvar(
    dc1_mw,
    dc1_pf
)

dc2_q_mvar = calculate_q_mvar(
    dc2_mw,
    dc2_pf
)


# ============================================================
# RUN PANDAPOWER MODEL
# ============================================================

print("\nRunning pandapower AC power-flow simulation...")

net = build_and_run_network(
    grid_voltage_kv,
    dc1_mw,
    dc1_q_mvar,
    dc2_mw,
    dc2_q_mvar,
    line_length_km,
    line_r,
    line_x,
    max_i_ka
)


# ============================================================
# CHECK CONVERGENCE
# ============================================================

if net is None:

    print("\n" + "=" * 62)
    print("SIMULATION DID NOT CONVERGE")
    print("=" * 62)

    print("\nThe power-flow solver could not find a valid operating point.")

    print("\nPossible causes:")
    print("- Data center loads are too large")
    print("- Transmission impedance is too high")
    print("- Grid voltage is too low")
    print("- The simplified network is too heavily stressed")

    print("\nTry reducing the load or line impedance.")

    raise SystemExit


# ============================================================
# EXTRACT PANDAPOWER RESULTS
# ============================================================

source_voltage_pu = net.res_bus.vm_pu.iloc[0]

dc1_voltage_pu = net.res_bus.vm_pu.iloc[1]

dc2_voltage_pu = net.res_bus.vm_pu.iloc[2]


source_voltage_kv = (
    source_voltage_pu * grid_voltage_kv
)

dc1_voltage_kv = (
    dc1_voltage_pu * grid_voltage_kv
)

dc2_voltage_kv = (
    dc2_voltage_pu * grid_voltage_kv
)


dc1_line_current_a = (
    net.res_line.i_ka.iloc[0] * 1000
)

dc2_line_current_a = (
    net.res_line.i_ka.iloc[1] * 1000
)


dc1_line_loading = (
    net.res_line.loading_percent.iloc[0]
)

dc2_line_loading = (
    net.res_line.loading_percent.iloc[1]
)


grid_p_mw = (
    net.res_ext_grid.p_mw.iloc[0]
)

grid_q_mvar = (
    net.res_ext_grid.q_mvar.iloc[0]
)


total_line_loss_mw = (
    net.res_line.pl_mw.sum()
)


# ============================================================
# NUMERICAL RESULTS
# ============================================================

print("\n" + "=" * 62)
print("SIMULATION SUCCESSFUL")
print("=" * 62)


print("\nDATA CENTER DEMAND")
print("-" * 62)

print(
    f"{'Data Center':<20}"
    f"{'MW':>10}"
    f"{'Mvar':>12}"
    f"{'PF':>10}"
)

print(
    f"{'Data Center 1':<20}"
    f"{dc1_mw:>10.2f}"
    f"{dc1_q_mvar:>12.2f}"
    f"{dc1_pf:>10.3f}"
)

print(
    f"{'Data Center 2':<20}"
    f"{dc2_mw:>10.2f}"
    f"{dc2_q_mvar:>12.2f}"
    f"{dc2_pf:>10.3f}"
)


print("\nBUS VOLTAGE RESULTS")
print("-" * 62)

print(
    f"{'Bus':<20}"
    f"{'Voltage (pu)':>15}"
    f"{'Voltage (kV)':>15}"
)

print(
    f"{'Grid Source':<20}"
    f"{source_voltage_pu:>15.4f}"
    f"{source_voltage_kv:>15.2f}"
)

print(
    f"{'Data Center 1':<20}"
    f"{dc1_voltage_pu:>15.4f}"
    f"{dc1_voltage_kv:>15.2f}"
)

print(
    f"{'Data Center 2':<20}"
    f"{dc2_voltage_pu:>15.4f}"
    f"{dc2_voltage_kv:>15.2f}"
)


print("\nLINE RESULTS")
print("-" * 62)

print(
    f"{'Line':<20}"
    f"{'Current (A)':>15}"
    f"{'Loading (%)':>15}"
)

print(
    f"{'Line to DC1':<20}"
    f"{dc1_line_current_a:>15.2f}"
    f"{dc1_line_loading:>15.2f}"
)

print(
    f"{'Line to DC2':<20}"
    f"{dc2_line_current_a:>15.2f}"
    f"{dc2_line_loading:>15.2f}"
)


print("\nGRID IMPACT")
print("-" * 62)

print(
    f"Total Data Center Demand: "
    f"{dc1_mw + dc2_mw:.2f} MW"
)

print(
    f"Grid Real Power Supply:   "
    f"{grid_p_mw:.2f} MW"
)

print(
    f"Grid Reactive Power:      "
    f"{grid_q_mvar:.2f} Mvar"
)

print(
    f"Transmission Losses:      "
    f"{total_line_loss_mw:.4f} MW"
)


# ============================================================
# GRAPH 1 - BUS VOLTAGES
# ============================================================

bus_names = [
    "Grid Source",
    "Data Center 1",
    "Data Center 2"
]

bus_voltages = [
    source_voltage_pu,
    dc1_voltage_pu,
    dc2_voltage_pu
]


plt.figure(figsize=(9, 5))

bars = plt.bar(
    bus_names,
    bus_voltages
)

plt.title(
    "Bus Voltage After Connecting Data Center Loads"
)

plt.ylabel(
    "Voltage (pu)"
)

plt.axhline(
    1.0,
    linestyle="--",
    label="Nominal Voltage"
)

plt.ylim(
    min(bus_voltages) - 0.02,
    1.02
)

plt.grid(
    axis="y",
    linestyle="--",
    alpha=0.4
)

plt.legend()


for bar in bars:

    value = bar.get_height()

    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value,
        f"{value:.4f} pu",
        ha="center",
        va="bottom"
    )


plt.tight_layout()

plt.show()


# ============================================================
# GRAPH 2 - LINE LOADING
# ============================================================

line_names = [
    "Line to DC1",
    "Line to DC2"
]

line_loading = [
    dc1_line_loading,
    dc2_line_loading
]


plt.figure(figsize=(9, 5))

bars = plt.bar(
    line_names,
    line_loading
)

plt.title(
    "Transmission Line Loading"
)

plt.ylabel(
    "Loading (%)"
)

plt.axhline(
    100,
    linestyle="--",
    label="Line Rating"
)

plt.grid(
    axis="y",
    linestyle="--",
    alpha=0.4
)

plt.legend()


for bar in bars:

    value = bar.get_height()

    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value,
        f"{value:.1f}%",
        ha="center",
        va="bottom"
    )


plt.tight_layout()

plt.show()


# ============================================================
# GRAPH 3 - SIMPLE LOAD GROWTH STUDY
# ============================================================

load_levels = np.arange(
    0,
    110,
    10
)

dc1_voltage_curve = []

dc2_voltage_curve = []


for load_percent in load_levels:

    scale = load_percent / 100

    test_net = build_and_run_network(
        grid_voltage_kv,

        dc1_mw * scale,
        dc1_q_mvar * scale,

        dc2_mw * scale,
        dc2_q_mvar * scale,

        line_length_km,
        line_r,
        line_x,
        max_i_ka
    )

    if test_net is None:

        dc1_voltage_curve.append(np.nan)
        dc2_voltage_curve.append(np.nan)

    else:

        dc1_voltage_curve.append(
            test_net.res_bus.vm_pu.iloc[1]
        )

        dc2_voltage_curve.append(
            test_net.res_bus.vm_pu.iloc[2]
        )


plt.figure(figsize=(10, 6))

plt.plot(
    load_levels,
    dc1_voltage_curve,
    marker="o",
    label="Data Center 1 Bus"
)

plt.plot(
    load_levels,
    dc2_voltage_curve,
    marker="o",
    label="Data Center 2 Bus"
)

plt.axhline(
    1.0,
    linestyle="--",
    label="Nominal Voltage"
)

plt.xlabel(
    "Data Center Load Level (%)"
)

plt.ylabel(
    "Bus Voltage (pu)"
)

plt.title(
    "Data Center Load Growth vs Bus Voltage"
)

plt.grid()

plt.legend()

plt.tight_layout()

plt.show()


