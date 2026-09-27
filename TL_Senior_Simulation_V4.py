import pandapower as pp
import pandapower.auxiliary
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import PercentFormatter

# ============================================================
# TEXAS DATA CENTER GRID IMPACT ANALYSIS
# Senior Design - Presentation Version
# ============================================================

VOLTAGE_MIN_PU = 0.95
VOLTAGE_MAX_PU = 1.05
LINE_LOADING_LIMIT = 100.0

NAVY = "#0B1F33"
BLUE = "#1976D2"
CYAN = "#26A6D1"
GREEN = "#2E7D32"
AMBER = "#F9A825"
RED = "#C62828"
LIGHT_GREEN = "#E9F5EC"
LIGHT_RED = "#FDECEC"
MID_GRAY = "#667085"
DARK = "#182230"
WHITE = "#FFFFFF"
GRID = "#D0D5DD"


def get_float(prompt, default, min_value=None, max_value=None):
    while True:
        raw = input(f"{prompt} [default = {default}]: ").strip()

        if raw == "":
            value = float(default)
        else:
            try:
                value = float(raw)
            except ValueError:
                print("  Please enter a valid number.")
                continue

        if min_value is not None and value < min_value:
            print(f"  Value must be at least {min_value}.")
            continue

        if max_value is not None and value > max_value:
            print(f"  Value must be no greater than {max_value}.")
            continue

        return value


def calculate_q_mvar(p_mw, power_factor):
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
    net = pp.create_empty_network()

    source_bus = pp.create_bus(net, vn_kv=grid_voltage_kv, name="Grid Source")
    dc1_bus = pp.create_bus(net, vn_kv=grid_voltage_kv, name="Data Center 1 Bus")
    dc2_bus = pp.create_bus(net, vn_kv=grid_voltage_kv, name="Data Center 2 Bus")

    pp.create_ext_grid(net, bus=source_bus, vm_pu=1.0, name="Utility Grid")

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


def print_header(title):
    print("\n" + "=" * 78)
    print(title.center(78))
    print("=" * 78)


def print_section(title):
    print("\n" + title)
    print("-" * 78)


def status_text(condition):
    return "PASS" if condition else "REVIEW"


def style_axis(ax):
    ax.set_facecolor(WHITE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MID_GRAY, labelsize=10)
    ax.grid(axis="y", linestyle="--", linewidth=0.8, alpha=0.45, color=GRID)
    ax.set_axisbelow(True)


def add_metric_card(fig, x, y, w, h, title, value, subtitle="", accent=BLUE):
    shadow = FancyBboxPatch(
        (x + 0.003, y - 0.004),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        transform=fig.transFigure,
        linewidth=0,
        facecolor="#000000",
        alpha=0.08,
        zorder=1
    )
    fig.add_artist(shadow)

    card = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.008,rounding_size=0.012",
        transform=fig.transFigure,
        linewidth=1.2,
        edgecolor="#E4E7EC",
        facecolor=WHITE,
        zorder=2
    )
    fig.add_artist(card)

    strip = FancyBboxPatch(
        (x, y),
        0.005,
        h,
        boxstyle="round,pad=0,rounding_size=0.004",
        transform=fig.transFigure,
        linewidth=0,
        facecolor=accent,
        zorder=3
    )
    fig.add_artist(strip)

    fig.text(
        x + 0.018,
        y + h * 0.68,
        title.upper(),
        fontsize=9,
        color=MID_GRAY,
        fontweight="bold",
        zorder=4
    )

    fig.text(
        x + 0.018,
        y + h * 0.34,
        value,
        fontsize=19,
        color=DARK,
        fontweight="bold",
        zorder=4
    )

    if subtitle:
        fig.text(
            x + 0.018,
            y + h * 0.10,
            subtitle,
            fontsize=8.5,
            color=MID_GRAY,
            zorder=4
        )


def create_dashboard(
    grid_voltage_kv,
    dc1_mw,
    dc2_mw,
    source_voltage_pu,
    dc1_voltage_pu,
    dc2_voltage_pu,
    dc1_line_loading,
    dc2_line_loading,
    dc1_line_current_a,
    dc2_line_current_a,
    grid_p_mw,
    grid_q_mvar,
    total_line_loss_mw,
    load_levels,
    dc1_voltage_curve,
    dc2_voltage_curve
):
    min_voltage = min(dc1_voltage_pu, dc2_voltage_pu)
    max_loading = max(dc1_line_loading, dc2_line_loading)

    voltage_ok = (
        VOLTAGE_MIN_PU <= dc1_voltage_pu <= VOLTAGE_MAX_PU
        and VOLTAGE_MIN_PU <= dc2_voltage_pu <= VOLTAGE_MAX_PU
    )
    loading_ok = max_loading <= LINE_LOADING_LIMIT
    overall_ok = voltage_ok and loading_ok

    fig = plt.figure(figsize=(16, 10), facecolor="#F7F9FC")
    fig.canvas.manager.set_window_title("Texas Data Center Grid Impact Dashboard")

    fig.text(
        0.055,
        0.955,
        "TEXAS DATA CENTER GRID IMPACT",
        fontsize=25,
        color=NAVY,
        fontweight="bold"
    )

    fig.text(
        0.055,
        0.925,
        "AC Power-Flow Analysis  •  Two-Data-Center Proof of Concept",
        fontsize=11.5,
        color=MID_GRAY
    )

    status_color = GREEN if overall_ok else RED
    status_word = "SYSTEM NORMAL" if overall_ok else "REVIEW REQUIRED"

    fig.text(
        0.945,
        0.95,
        status_word,
        ha="right",
        va="center",
        fontsize=11,
        color=status_color,
        fontweight="bold",
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor=LIGHT_GREEN if overall_ok else LIGHT_RED,
            edgecolor=status_color,
            linewidth=1.0
        )
    )

    total_demand = dc1_mw + dc2_mw
    loss_percent = (total_line_loss_mw / grid_p_mw * 100) if grid_p_mw != 0 else 0

    card_y = 0.795
    card_h = 0.095
    card_w = 0.166
    card_gap = 0.014
    card_xs = [0.055 + i * (card_w + card_gap) for i in range(5)]

    add_metric_card(
        fig, card_xs[0], card_y, card_w, card_h,
        "Total DC Demand",
        f"{total_demand:.1f} MW",
        f"DC1 {dc1_mw:.0f} MW  •  DC2 {dc2_mw:.0f} MW",
        BLUE
    )

    add_metric_card(
        fig, card_xs[1], card_y, card_w, card_h,
        "Minimum Voltage",
        f"{min_voltage:.4f} pu",
        f"Target {VOLTAGE_MIN_PU:.2f}–{VOLTAGE_MAX_PU:.2f} pu",
        GREEN if voltage_ok else RED
    )

    add_metric_card(
        fig, card_xs[2], card_y, card_w, card_h,
        "Max Line Loading",
        f"{max_loading:.1f}%",
        "Limit 100%",
        GREEN if loading_ok else RED
    )

    add_metric_card(
        fig, card_xs[3], card_y, card_w, card_h,
        "Grid Supply",
        f"{grid_p_mw:.1f} MW",
        f"{grid_q_mvar:.1f} Mvar reactive",
        CYAN
    )

    add_metric_card(
        fig, card_xs[4], card_y, card_w, card_h,
        "Transmission Losses",
        f"{total_line_loss_mw:.3f} MW",
        f"{loss_percent:.3f}% of grid supply",
        AMBER
    )

    ax_voltage = fig.add_axes([0.065, 0.485, 0.415, 0.245])
    ax_loading = fig.add_axes([0.535, 0.485, 0.405, 0.245])
    ax_growth = fig.add_axes([0.065, 0.095, 0.875, 0.275])

    # BUS VOLTAGE
    style_axis(ax_voltage)

    bus_names = ["Grid Source", "Data Center 1", "Data Center 2"]
    bus_voltages = [source_voltage_pu, dc1_voltage_pu, dc2_voltage_pu]

    voltage_colors = [
        NAVY,
        GREEN if VOLTAGE_MIN_PU <= dc1_voltage_pu <= VOLTAGE_MAX_PU else RED,
        GREEN if VOLTAGE_MIN_PU <= dc2_voltage_pu <= VOLTAGE_MAX_PU else RED
    ]

    ax_voltage.axhspan(
        VOLTAGE_MIN_PU,
        VOLTAGE_MAX_PU,
        color=GREEN,
        alpha=0.08
    )

    bars = ax_voltage.bar(
        bus_names,
        bus_voltages,
        width=0.56,
        color=voltage_colors,
        edgecolor="none"
    )

    ax_voltage.axhline(
        1.0,
        color=NAVY,
        linestyle="--",
        linewidth=1.2,
        alpha=0.75
    )

    ymin = min(0.90, min(bus_voltages) - 0.025)
    ymax = max(1.06, max(bus_voltages) + 0.025)
    ax_voltage.set_ylim(ymin, ymax)

    ax_voltage.set_title(
        "Bus Voltage Performance",
        loc="left",
        fontsize=14,
        fontweight="bold",
        color=DARK,
        pad=14
    )
    ax_voltage.set_ylabel("Voltage (pu)", color=MID_GRAY, fontsize=10)

    # Clean direct labels instead of a crowded legend
    ax_voltage.text(
        0.02,
        0.95,
        f"Acceptable Operating Range: {VOLTAGE_MIN_PU:.2f} - {VOLTAGE_MAX_PU:.2f} pu",
        transform=ax_voltage.transAxes,
        fontsize=8.5,
        color=GREEN,
        fontweight="bold",
        va="top"
    )

    ax_voltage.text(
        0.98,
        1.003,
        "Nominal: 1.00 pu",
        transform=ax_voltage.get_yaxis_transform(),
        fontsize=8,
        color=NAVY,
        ha="right",
        va="bottom"
    )

    for bar, value in zip(bars, bus_voltages):
        ax_voltage.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.004,
            f"{value:.4f} pu",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=DARK
        )

    # LINE LOADING
    style_axis(ax_loading)

    line_names = ["Line → DC1", "Line → DC2"]
    loadings = [dc1_line_loading, dc2_line_loading]
    currents = [dc1_line_current_a, dc2_line_current_a]

    loading_colors = [
        GREEN if dc1_line_loading <= LINE_LOADING_LIMIT else RED,
        GREEN if dc2_line_loading <= LINE_LOADING_LIMIT else RED
    ]

    bars = ax_loading.bar(
        line_names,
        loadings,
        width=0.52,
        color=loading_colors,
        edgecolor="none"
    )

    ax_loading.axhspan(
        LINE_LOADING_LIMIT,
        max(120, max(loadings) * 1.15),
        color=RED,
        alpha=0.06
    )

    ax_loading.axhline(
        LINE_LOADING_LIMIT,
        color=RED,
        linestyle="--",
        linewidth=1.4,
        label="100% line rating"
    )

    ax_loading.set_ylim(0, max(115, max(loadings) * 1.22))
    ax_loading.set_title(
        "Transmission Line Utilization",
        loc="left",
        fontsize=14,
        fontweight="bold",
        color=DARK,
        pad=14
    )
    ax_loading.set_ylabel("Loading (%)", color=MID_GRAY, fontsize=10)
    ax_loading.yaxis.set_major_formatter(PercentFormatter(xmax=100))

    for bar, loading, current in zip(bars, loadings, currents):
        ax_loading.text(
            bar.get_x() + bar.get_width() / 2,
            loading + max(2.0, max(loadings) * 0.025),
            f"{loading:.1f}%\n{current:.0f} A",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color=DARK
        )

    ax_loading.legend(loc="upper left", frameon=False, fontsize=8.5)

    # LOAD GROWTH
    style_axis(ax_growth)

    ax_growth.axhspan(
        VOLTAGE_MIN_PU,
        VOLTAGE_MAX_PU,
        color=GREEN,
        alpha=0.07,
        label="Acceptable voltage band"
    )

    ax_growth.plot(
        load_levels,
        dc1_voltage_curve,
        marker="o",
        markersize=5,
        linewidth=2.4,
        color=BLUE,
        label="Data Center 1 Bus"
    )

    ax_growth.plot(
        load_levels,
        dc2_voltage_curve,
        marker="o",
        markersize=5,
        linewidth=2.4,
        color=CYAN,
        label="Data Center 2 Bus"
    )

    ax_growth.axhline(
        1.0,
        color=NAVY,
        linestyle="--",
        linewidth=1.0,
        alpha=0.75
    )

    ax_growth.axvline(
        100,
        color=AMBER,
        linestyle=":",
        linewidth=1.8,
        label="Current entered load"
    )

    ax_growth.scatter(
        [100, 100],
        [dc1_voltage_pu, dc2_voltage_pu],
        s=65,
        color=[BLUE, CYAN],
        edgecolors=WHITE,
        linewidths=1.2,
        zorder=5
    )

    ax_growth.set_title(
        "Load Growth Sensitivity — Bus Voltage vs Data Center Demand",
        loc="left",
        fontsize=14,
        fontweight="bold",
        color=DARK,
        pad=14
    )
    ax_growth.set_xlabel(
        "Combined Data Center Load Level (%)",
        color=MID_GRAY,
        fontsize=10
    )
    ax_growth.set_ylabel("Bus Voltage (pu)", color=MID_GRAY, fontsize=10)
    ax_growth.set_xlim(0, max(load_levels))

    all_curve_values = np.array(
        list(dc1_voltage_curve) + list(dc2_voltage_curve),
        dtype=float
    )
    finite_values = all_curve_values[np.isfinite(all_curve_values)]
    lower_bound = 0.90 if finite_values.size == 0 else min(0.90, finite_values.min() - 0.02)
    ax_growth.set_ylim(lower_bound, 1.055)

    ax_growth.legend(
        loc="lower left",
        ncol=4,
        frameon=False,
        fontsize=8.5
    )

    fig.text(
        0.055,
        0.035,
        f"Model: Newton-Raphson AC power flow  |  Nominal voltage: {grid_voltage_kv:.0f} kV  |  "
        f"Voltage criterion: {VOLTAGE_MIN_PU:.2f}–{VOLTAGE_MAX_PU:.2f} pu  |  "
        f"Line criterion: ≤ {LINE_LOADING_LIMIT:.0f}%",
        fontsize=8.8,
        color=MID_GRAY
    )

    fig.text(
        0.945,
        0.035,
        "Senior Design • Proof-of-Concept Simulation",
        ha="right",
        fontsize=8.8,
        color=MID_GRAY
    )

    plt.show()


def main():
    print_header("TEXAS DATA CENTER GRID IMPACT ANALYSIS")

    print(
        "\nPandapower AC power-flow proof-of-concept for two data centers\n"
        "connected to a simplified utility grid."
    )
    print("\nPress Enter at any prompt to use the suggested default value.")

    print_section("GRID SETTINGS")

    grid_voltage_kv = get_float("Grid voltage (kV)", 138, min_value=1)
    line_length_km = get_float(
        "Transmission line length to each data center (km)",
        10,
        min_value=0.001
    )
    line_r = get_float("Line resistance (ohm/km)", 0.05, min_value=0)
    line_x = get_float("Line reactance (ohm/km)", 0.40, min_value=0)
    max_i_ka = get_float("Line current rating (kA)", 1.0, min_value=0.001)

    print_section("DATA CENTER 1")
    dc1_mw = get_float("Real power demand (MW)", 100, min_value=0)
    dc1_pf = get_float("Power factor", 0.95, min_value=0.01, max_value=1.0)

    print_section("DATA CENTER 2")
    dc2_mw = get_float("Real power demand (MW)", 150, min_value=0)
    dc2_pf = get_float("Power factor", 0.95, min_value=0.01, max_value=1.0)

    dc1_q_mvar = calculate_q_mvar(dc1_mw, dc1_pf)
    dc2_q_mvar = calculate_q_mvar(dc2_mw, dc2_pf)

    print_section("RUNNING SIMULATION")
    print("Solving Newton-Raphson AC power flow...")

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

    if net is None:
        print_header("SIMULATION DID NOT CONVERGE")
        print(
            "\nThe power-flow solver could not find a valid operating point.\n"
            "Try reducing the data center loads, reducing line impedance,\n"
            "or checking the selected grid voltage and current rating."
        )
        return

    source_voltage_pu = net.res_bus.vm_pu.iloc[0]
    dc1_voltage_pu = net.res_bus.vm_pu.iloc[1]
    dc2_voltage_pu = net.res_bus.vm_pu.iloc[2]

    source_voltage_kv = source_voltage_pu * grid_voltage_kv
    dc1_voltage_kv = dc1_voltage_pu * grid_voltage_kv
    dc2_voltage_kv = dc2_voltage_pu * grid_voltage_kv

    dc1_line_current_a = net.res_line.i_ka.iloc[0] * 1000
    dc2_line_current_a = net.res_line.i_ka.iloc[1] * 1000

    dc1_line_loading = net.res_line.loading_percent.iloc[0]
    dc2_line_loading = net.res_line.loading_percent.iloc[1]

    grid_p_mw = net.res_ext_grid.p_mw.iloc[0]
    grid_q_mvar = net.res_ext_grid.q_mvar.iloc[0]
    total_line_loss_mw = net.res_line.pl_mw.sum()

    voltage_ok = (
        VOLTAGE_MIN_PU <= dc1_voltage_pu <= VOLTAGE_MAX_PU
        and VOLTAGE_MIN_PU <= dc2_voltage_pu <= VOLTAGE_MAX_PU
    )
    loading_ok = (
        dc1_line_loading <= LINE_LOADING_LIMIT
        and dc2_line_loading <= LINE_LOADING_LIMIT
    )
    overall_ok = voltage_ok and loading_ok

    print_header("SIMULATION RESULTS")
    print(f"Overall System Status : {status_text(overall_ok)}")
    print(f"Total Data Center Load: {dc1_mw + dc2_mw:.2f} MW")
    print(f"Grid Real Power Supply: {grid_p_mw:.2f} MW")
    print(f"Grid Reactive Power   : {grid_q_mvar:.2f} Mvar")
    print(f"Transmission Losses   : {total_line_loss_mw:.4f} MW")

    print_section("DATA CENTER DEMAND")
    print(f"{'Load':<22}{'P (MW)':>12}{'Q (Mvar)':>14}{'PF':>10}")
    print(f"{'Data Center 1':<22}{dc1_mw:>12.2f}{dc1_q_mvar:>14.2f}{dc1_pf:>10.3f}")
    print(f"{'Data Center 2':<22}{dc2_mw:>12.2f}{dc2_q_mvar:>14.2f}{dc2_pf:>10.3f}")

    print_section("BUS VOLTAGE PERFORMANCE")
    print(f"{'Bus':<22}{'Voltage (pu)':>15}{'Voltage (kV)':>15}{'Status':>12}")
    print(
        f"{'Grid Source':<22}{source_voltage_pu:>15.4f}"
        f"{source_voltage_kv:>15.2f}{'REFERENCE':>12}"
    )
    print(
        f"{'Data Center 1':<22}{dc1_voltage_pu:>15.4f}"
        f"{dc1_voltage_kv:>15.2f}"
        f"{status_text(VOLTAGE_MIN_PU <= dc1_voltage_pu <= VOLTAGE_MAX_PU):>12}"
    )
    print(
        f"{'Data Center 2':<22}{dc2_voltage_pu:>15.4f}"
        f"{dc2_voltage_kv:>15.2f}"
        f"{status_text(VOLTAGE_MIN_PU <= dc2_voltage_pu <= VOLTAGE_MAX_PU):>12}"
    )

    print_section("TRANSMISSION LINE PERFORMANCE")
    print(f"{'Line':<22}{'Current (A)':>15}{'Loading (%)':>15}{'Status':>12}")
    print(
        f"{'Line to DC1':<22}{dc1_line_current_a:>15.2f}"
        f"{dc1_line_loading:>15.2f}"
        f"{status_text(dc1_line_loading <= LINE_LOADING_LIMIT):>12}"
    )
    print(
        f"{'Line to DC2':<22}{dc2_line_current_a:>15.2f}"
        f"{dc2_line_loading:>15.2f}"
        f"{status_text(dc2_line_loading <= LINE_LOADING_LIMIT):>12}"
    )

    print_section("LOAD-GROWTH STUDY")
    print("Running 0%–150% load sensitivity sweep...")

    load_levels = np.arange(0, 160, 10)
    dc1_voltage_curve = []
    dc2_voltage_curve = []

    for load_percent in load_levels:
        scale = load_percent / 100.0

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
            dc1_voltage_curve.append(test_net.res_bus.vm_pu.iloc[1])
            dc2_voltage_curve.append(test_net.res_bus.vm_pu.iloc[2])

    print("Dashboard ready.")

    create_dashboard(
        grid_voltage_kv,
        dc1_mw,
        dc2_mw,
        source_voltage_pu,
        dc1_voltage_pu,
        dc2_voltage_pu,
        dc1_line_loading,
        dc2_line_loading,
        dc1_line_current_a,
        dc2_line_current_a,
        grid_p_mw,
        grid_q_mvar,
        total_line_loss_mw,
        load_levels,
        dc1_voltage_curve,
        dc2_voltage_curve
    )


if __name__ == "__main__":
    main()
