"""
A Series of Unit tests for rf_station.c/h
"""

import accelerator as acc

import numpy as np
import matplotlib.pylab as plt
import scipy.linalg as linalg
from scipy import stats

def unit_phase_shift():
    """
    Unit test for Phase_Shift. Run numerical simulation with several phase shift values,
    measure the phase difference between the input and output signals and return
    a PASS/FAIL boolean according to the error on that comparison.
    """

    trang = np.arange(0.0, 1.0, 0.01)

    nt = len(trang)

    signal_in = np.exp(4j*np.pi*trang)
    thetas = np.arange(0, np.pi, np.pi/6.0)

    out = np.zeros(nt, dtype=np.complex)
    out_phase = np.zeros(nt, dtype=np.double)
    in_phase = np.zeros(nt, dtype=np.double)

    # Initialize PASS variable
    phase_shift_pass = True

    for theta in thetas:
        for i in xrange(nt):
            out[i] = acc.Phase_Shift(signal_in[i], theta)
            out_phase[i] = np.angle(out[i])
            in_phase[i] = np.angle(signal_in[i])

        # Calculate phase difference
        # Unwrap phase
        out_phase_unw = np.unwrap(out_phase)
        in_phase_unw = np.unwrap(in_phase)
        # Average phase
        out_phase_avg = np.average(out_phase_unw)
        in_phase_avg = np.average(in_phase_unw)
        # Calculate measured phase difference
        theta_meas = np.average(out_phase_avg - in_phase_avg)
        # Calculate error
        error = theta_meas - theta

        # If error > threshold, turn phase_shift_pass to False
        pass_now = error < 1e-8
        phase_shift_pass = phase_shift_pass & pass_now

        # Plot and record c parameter for label
        label_text = r'$\theta=$%.1f' % theta

        plt.plot(trang, out.real, label=label_text)

    plt.title("Phase shift test", fontsize=40, y=1.01)
    plt.xlabel('Time [s]', fontsize=30)
    plt.ylabel('Real Part [Normalized]', fontsize=30)
    plt.legend(loc='upper right')
    plt.show()

    # Return PASS/FAIL
    return phase_shift_pass

def unit_fpga(Tstep=0.01):
    """
    Unit test for FPGA controller.
    Perform test where the FPGA controller transfer function is evaluated.
    The FPGA drive signal is analyzed, proportional and integral gains are deduced,
    compared with the model settings, and a PASS/FAIL boolean is return based on that comparison.
    """

    # Get a pointer to the FPGA C-structure
    fpga = acc.FPGA()

    # Initial settings
    kp = -5.0
    ki = -3.0
    set_point_start = 0.0 + 0.0j  # Start with 0
    set_point_step = 1.0 + 0.0j  # Apply step on real component
    cav_in = 0.0 + 0.0j
    out_sat = 200   # Set FPGA saturation limit high not to reach that point
    open_loop = 0   # Closed-loop setting (apply control to drive signal)

    # Fill in C data structure with settings
    acc.FPGA_Allocate_In(fpga, kp, ki, set_point_start, out_sat, Tstep)

    # Allocate State structure and initialize
    fpga_state = acc.FPGA_State()
    fpga_state.drive = 0.0 + 0.0j
    fpga_state.state = 0.0 + 0.0j
    fpga_state.openloop = 0

    # Total simulation time for test (seconds)
    Tmax = 2.0

    # Buld a time axis
    trang = np.arange(0.0, Tmax, Tstep)

    nt = len(trang)  # Number of points

    # Initialize complex vectors
    error = np.zeros(nt, dtype=np.complex)
    drive = np.zeros(nt, dtype=np.complex)
    state = np.zeros(nt, dtype=np.complex)

    # Determine when to step set-point
    sp_step = int(nt*0.1)

    # Run time-series simulation
    for i in xrange(nt):

        # Apply step on set-point at sp_step simulation time
        if i == sp_step:
            fpga.set_point = set_point_step

        # Call FPGA_Step and record signals of interest
        error[i] = acc.FPGA_Step(fpga, cav_in, fpga_state)
        drive[i] = fpga_state.drive
        state[i] = fpga_state.state

    # Measure kp and ki
    kp_measured = (drive[sp_step] - drive[sp_step-1]+set_point_step*ki*Tstep)/-set_point_step
    kp_text = r'$k_{\rm p}$'+' set to: %.1f, measured: %.1f' % (np.real(kp), np.real(kp_measured))
    slope, b = np.polyfit(trang[sp_step:-1], drive[sp_step:-1], 1)  # Slope
    ki_measured = slope/-np.abs(set_point_step)
    ki_text = r'$k_{\rm i}$'+' set to: %.1f, measured: %.1f' % (np.real(ki), np.real(ki_measured))

    # Plot
    plt.plot(trang, np.real(drive), '-r', label='Drive')
    plt.plot(trang, np.real(error), '-+', label='Error')
    plt.plot(trang, np.real(state), '-*', label='Integrator state')

    plt.title("FPGA Unit Test", fontsize=40, y=1.01)
    plt.xlabel('Time [s]', fontsize=30)
    plt.ylabel('Amplitude [Unitless]', fontsize=30)
    plt.legend(loc='upper right')
    plt.ylim([-2.2, 13])

    # Add text with results on plot
    plt.text(1, 6.5, kp_text, verticalalignment='top', fontsize=30)
    plt.text(1, 5.5, ki_text, verticalalignment='top', fontsize=30)
    plt.rc('font', **{'size': 15})

    plt.show()

    # Evaluate PASS/FAIL for unit test (error must be 0)
    kp_error = np.abs(kp_measured - kp)
    ki_error = np.abs(ki_measured - ki)

    if (kp_error < 1e-12) and (ki_error < 1e-12):
        unit_fpga_pass = True
    else:
        unit_fpga_pass = False

    # PASS == True
    return unit_fpga_pass

def unit_saturate():
    """
    Unit test for Saturation function. It runs numerical simulations for several values of the clip harshness parameter
    and plots the results. This is not a PASS/FAIL test and just intended to provide qualitative evidence.
    """

    # Iterate over harshness parameter c
    for c in np.arange(1.0, 6, 1.0):
        # Input vector
        inp = np.arange(0.0, 10.0, 0.1, dtype=np.complex)
        # Output vector
        oup = np.zeros(inp.shape, dtype=np.complex)

        # Boolean indicating finding percentile reach
        found = False
        V_sat = max(inp)

        # Sweep input
        for i in xrange(len(inp)):
            oup[i] = acc.Saturate(inp[i], c)
            if (found == False) and (oup[i].real >= 0.95):
                V_sat = inp[i]
                found = True

        # Plot and record c parameter for label
        label_text = "c = %.1f" % c
        print '   for c = %.1f -> V_sat = %.2f' % (c, V_sat.real)
        plt.plot(inp.real, oup.real, label=label_text)

    # Plot
    plt.title("Saturation Test", fontsize=40, y=1.01)
    plt.xlabel(r'$|\vec V_{\rm in}| [\rm V]$', fontsize=30)
    plt.ylabel(r'$|\vec V_{\rm out}| [\rm Normalized]$', fontsize=30)

    # Add equation text on plot
    plt.text(5, 0.4, r'$\vec V_{\rm out} = \vec V_{\rm in} \cdot \left(1 + |\vec V_{\rm in}|^c\right)^{-1/c}$', fontsize=30)

    # Adjust legend placement and vertical axis limits
    plt.legend(loc=7)
    plt.ylim([0, 1.1])

    # Show plot
    plt.show()

#
# Unit test for SSA
#

def unit_SSA(showplots=True, TOL=1.0e-14):
    """
    Unit test for Solid-State Amplifier funtion.
    Performs the step response of the SSA (which included a low-pass filter + Saturation) and plots the results.
    This is not a PASS/FAIL test and just intended to provide qualitative evidence, but it could potentially be compared
    with the real SSA in use.
    """

    # Import JSON parser module
    from get_configuration import Get_SWIG_RF_Station

    # Configuration file for specific test configuration
    # (to be appended to standard test cavity configuration)
    test_file = "source/configfiles/unit_tests/SSA_test.json"

    # Get SWIG-wrapped C handles for RF Station
    rf_station, Tstep, fund_mode_dict = Get_SWIG_RF_Station(test_file, Verbose=False)

    # Simulation duration
    Tmax = 1e-6

    # Create time vector
    trang = np.arange(0, Tmax, Tstep)

    # Number of points
    nt = len(trang)

    # Initialize vectors for test
    sout = np.zeros(nt, dtype=np.complex)   # Overall cavity accelerating voltage

    # Set drive signal to 60% of full power
    drive = rf_station.C_Pointer.PAscale*0.6

    # Run numerical simulation
    for i in xrange(1, nt):
        sout[i] = acc.SSA_Step(rf_station.C_Pointer, drive, rf_station.State)

    # Format plot
    plt.plot(trang, np.abs(sout), '-', label='SSA output', linewidth=3)
    plt.ticklabel_format(style='sci', axis='x', scilimits=(1, 0))
    plt.title('SSA Test', fontsize=40, y=1.01)
    plt.xlabel('Time [s]', fontsize=30)
    plt.ylabel('Amplitude '+r'[$\sqrt{W}$]', fontsize=30)
    plt.legend(loc='upper right')

    plt.ylim([0, 50])

    plt.show()

def run_RF_Station_test(Tmax, test_file):

    # Import JSON parser module
    from get_configuration import Get_SWIG_RF_Station

    # Configuration file for specific test configuration
    # (to be appended to standard test cavity configuration)
    rf_station, Tstep, fund_mode_dict = Get_SWIG_RF_Station(test_file, Verbose=False)

    # Create time vector
    trang = np.arange(0, Tmax, Tstep)

    # Number of points
    nt = len(trang)

    # Initialize vectors for test
    E_probe = np.zeros(nt, dtype=np.complex)
    E_reverse = np.zeros(nt, dtype=np.complex)
    E_fwd = np.zeros(nt, dtype=np.complex)
    set_point = np.zeros(nt, dtype=np.complex)

    # Run Numerical Simulation
    for i in xrange(1, nt):
        cav_v = acc.RF_Station_Step(rf_station.C_Pointer, 0.0, 0.0, 0.0, rf_station.State)
        set_point[i] = rf_station.C_Pointer.fpga.set_point
        E_probe[i] = rf_station.State.cav_state.E_probe
        E_reverse[i] = rf_station.State.cav_state.E_reverse
        E_fwd[i] = rf_station.State.cav_state.E_fwd

    fund_k_probe = fund_mode_dict['k_probe']
    fund_k_drive = fund_mode_dict['k_drive']
    fund_k_em = fund_mode_dict['k_em']

    plt.plot(trang*1e3, np.abs(E_reverse/fund_k_em), '-', label=r'Reverse $\left(\vec E_{\rm reverse}\right)$', linewidth=2)
    plt.plot(trang*1e3, np.abs(E_fwd)*fund_k_drive, '-', label=r'Forward $\left(\vec E_{\rm fwd}\right)$', linewidth=2)
    plt.plot(trang*1e3, np.abs(set_point/fund_k_probe), label=r'Set-point $\left(\vec E_{\rm sp}\right)$', linewidth=2)
    plt.plot(trang*1e3, np.abs(E_probe/fund_k_probe), '-', label=r'Probe $\left(\vec E_{\rm probe}\right)$', linewidth=2)

    plt.title('RF Station Test', fontsize=40, y=1.01)
    plt.xlabel('Time [ms]', fontsize=30)
    plt.ylabel('Amplitude [V]', fontsize=30)
    plt.legend(loc='upper right')
    plt.rc('font', **{'size': 25})

    # Show plot
    plt.show()


def unit_RF_Station():
    """
    Unit test for rf_station.c/h
    It emulates a cavity fill-up, where forward signal is saturated and
    cavity field reaching steady-state with controller stabilizing the field
    around the set point. Plot is generated for qualitative analysis.
    This is not a PASS/FAIL test but responds to the typical RF Station behavior.
    """
    Tmax = 0.05

    test_file = "source/configfiles/unit_tests/cavity_test_step1.json"

    run_RF_Station_test(Tmax, test_file)


######################################
#
# Now execute the tests...
#
######################################

def perform_tests():
    """
    Perform all unit tests for rf_station.c/h and return PASS/FAIL boolean (AND'd result of all tests).
    """

    print "\n****\nTesting Phase_Shift..."
    phase_shift_pass = unit_phase_shift()
    if (phase_shift_pass):
        result = 'PASS'
    else:
        result = 'FAIL'
    print ">>> " + result

    plt.figure()

    print "\n****\nTesting FPGA PI controller..."
    fpga_pass = unit_fpga()
    if (fpga_pass):
        result = 'PASS'
    else:
        result = 'FAIL'
    print ">>> " + result

    # This is not a PASS/FAIL test
    print "\n****\nTesting Saturate..."
    unit_saturate()
    print ">>> (Visual inspection only)\n"

    # This is not a PASS/FAIL test
    print "\n****\nTesting SSA..."
    unit_SSA()
    print ">>> (Visual inspection only)\n"

    plt.figure()

    # This is not a PASS/FAIL test
    print "\n****\nTesting RF Station..."
    unit_RF_Station()
    print ">>> (Visual inspection only)\n"

    plt.figure()

    return fpga_pass & phase_shift_pass

if __name__ == "__main__":
    plt.close('all')
    perform_tests()
