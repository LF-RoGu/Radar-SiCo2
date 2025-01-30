import numpy as np
import matplotlib.pyplot as plt

R_zero_20 = 100
sigma_20_dB = 20
sigma_0_dB = 0

sigma_20_lin = 10**(sigma_20_dB/10)
sigma_0_lin = 10**(sigma_0_dB/10)

R_zero_10 = R_zero_20 * (sigma_0_lin/sigma_20_lin)**(1/4)


phi = np.arange(-90, 90, 1)
G_phi_dB = -0.0055*phi**2 + 17.5
G_phi_lin = 10**(G_phi_dB/10)

R_phi_20 = R_zero_20 * (G_phi_lin/G_phi_lin[int(len(phi)/2)])**(1/4)
R_phi_10 = R_zero_10 * (G_phi_lin/G_phi_lin[int(len(phi)/2)])**(1/4)




fig, axes = plt.subplots(2, 1, figsize=(8, 8))
ax1, ax2 = axes

ax1.clear()
ax1.set_xlim(-90, 90)
ax1.set_ylim(-40, 20)
ax1.set_title("Gain vs. angle")
ax1.set_xlabel("Phi (deg)")
ax1.set_ylabel("G (dBi)")
ax1.plot(phi, G_phi_dB)

ax2.clear()
ax2.set_xlim(-90, 90)
ax2.set_ylim(0, 110)
ax2.set_title("Coverage vs. angle")
ax2.set_xlabel("Phi (deg)")
ax2.set_ylabel("Coverage (m)")
ax2.plot(phi, R_phi_20, label="20dBsm target")
ax2.plot(phi, R_phi_10, label="0dBsm target")
ax2.legend()


plt.show()