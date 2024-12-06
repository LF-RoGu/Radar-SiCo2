import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation
import random
import numpy as np

# Constants
c = 3e8  # Speed of light (m/s)
f = 24e9  # Radar carrier frequency (Hz)
v_s = 5  # Speed of the square (m/s)

def create_kalman_filter(initial_x, initial_y):
    """Create and initialize a Kalman filter for a dot."""
    from filterpy.kalman import KalmanFilter
    kf = KalmanFilter(dim_x=4, dim_z=2)  # 4 states (x, y, vx, vy), 2 measurements (x, y)
    kf.F = np.array([[1, 0, 1, 0],  # State transition matrix
                     [0, 1, 0, 1],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]])
    kf.H = np.array([[1, 0, 0, 0],  # Measurement function
                     [0, 1, 0, 0]])
    kf.P *= 10  # Initial covariance matrix
    kf.R = np.array([[0.1, 0],  # Measurement noise
                     [0, 0.1]])
    kf.Q = np.eye(4) * 0.01  # Process noise
    kf.x = np.array([[initial_x],  # Initial state
                     [initial_y],
                     [0],
                     [0]])
    return kf

def calculate_doppler_and_radial_speed(square_position, dot_position):
    """
    Calculate the radial speed and Doppler shift for a detected dot.

    Parameters:
    - square_position: Tuple (x, y) of the square's position.
    - dot_position: Tuple (x, y) of the dot's position.

    Returns:
    - radial_speed: Radial speed (m/s) of the dot relative to the square.
    - doppler_shift: Doppler frequency shift (Hz) due to the radial speed.
    """
    # Relative position vector
    dx = dot_position[0] - square_position[0]
    dy = dot_position[1] - square_position[1]
    distance = np.sqrt(dx**2 + dy**2)
    
    # Avoid division by zero for extremely close dots
    if distance == 0:
        return 0, 0

    # Angle between the radar's motion and the line to the dot
    theta = np.arctan2(dy, dx)
    
    # Radial speed (m/s)
    radial_speed = v_s * np.cos(theta)
    
    # Doppler frequency shift (Hz)
    doppler_shift = (2 * f * radial_speed) / c

    return radial_speed, doppler_shift

# Main configuration
plot_x_limits = [0, 20]
plot_y_limits = [0, 10]
grid_spacing = 1

# Square configuration
square_config = {
    'width': 3,
    'height': 1,
    'start_x': 0,
    'start_y': 5,
    'color': 'blue'
}

# Wedge configuration
wedge_config = {
    'radius': 12,
    'angle': 30,
    'start_x': square_config['start_x'] + square_config['width'],
    'start_y': square_config['start_y'] + square_config['height'] / 2,
    'color': 'red',
    'alpha': 0.5
}

# Dots configuration
dots_start_x = 10
num_dots = 15

# Generate random dots
dots = [
    (random.uniform(dots_start_x, plot_x_limits[1]), random.uniform(plot_y_limits[0], plot_y_limits[1]))
    for _ in range(num_dots)
]

# Detected dots and their Kalman filters
detected_dots = []
displayed_dots = set()  # To track dots whose Doppler results have already been displayed
kalman_filters = {}

# Create the figure and axes
fig, ax = plt.subplots()
ax.set_xlim(plot_x_limits[0], plot_x_limits[1])
ax.set_ylim(plot_y_limits[0], plot_y_limits[1])

# Plot the dots
dot_plots = {}
for dot in dots:
    dot_plots[dot] = ax.plot(dot[0], dot[1], 'o', color='green')  # Static dots in green

# Add square and wedge
square = patches.Rectangle(
    (square_config['start_x'], square_config['start_y']),
    square_config['width'], square_config['height'],
    color=square_config['color']
)
ax.add_patch(square)

wedge = patches.Wedge(
    (wedge_config['start_x'], wedge_config['start_y']),
    wedge_config['radius'],
    -wedge_config['angle'] / 2,
    wedge_config['angle'] / 2,
    color=wedge_config['color'],
    alpha=wedge_config['alpha']
)
ax.add_patch(wedge)

def is_point_in_wedge(point, wedge_center, wedge_radius, wedge_angle, wedge_direction):
    """Check if a point is within the wedge's detection area."""
    px, py = point
    cx, cy = wedge_center
    dx, dy = px - cx, py - cy
    distance = np.sqrt(dx**2 + dy**2)
    if distance > wedge_radius:
        return False

    angle_to_point = np.degrees(np.arctan2(dy, dx))
    relative_angle = (angle_to_point - wedge_direction) % 360
    if relative_angle > 180:
        relative_angle -= 360

    return -wedge_angle / 2 <= relative_angle <= wedge_angle / 2

def update(frame):
    """
    Update function for the animation. Detects and tracks dots using Kalman Filter,
    calculates Doppler shift and radial speed for detected dots, and marks detected dots with crosses.
    """
    global detected_dots, displayed_dots, kalman_filters

    # Move the square
    square.set_x(frame)

    # Move the wedge
    wedge_center = (frame + square_config['width'], wedge_config['start_y'])
    wedge.set_center(wedge_center)

    # Check for new detections
    new_detections = [
        dot for dot in dots if is_point_in_wedge(
            dot, wedge_center, wedge_config['radius'], wedge_config['angle'], 0
        )
    ]

    for dot in new_detections:
        if dot not in detected_dots:
            # Initialize Kalman filter for new detection
            kalman_filters[dot] = create_kalman_filter(dot[0], dot[1])
            detected_dots.append(dot)

            # Mark detected dot with a cross
            ax.plot(dot[0], dot[1], 'x', color='red')  # Cross for detected dots

    # Predict and update Kalman filters for tracked dots and calculate Doppler effect
    for dot, kf in kalman_filters.items():
        if dot not in displayed_dots:
            kf.predict()
            pred_x, pred_y = kf.x[0, 0], kf.x[1, 0]

            # Calculate Doppler effect and radial speed
            radial_speed, doppler_shift = calculate_doppler_and_radial_speed(wedge_center, (pred_x, pred_y))
            print(f"Dot at {dot}: Radial Speed = {radial_speed:.2f} m/s, Doppler Shift = {doppler_shift:.2f} Hz")

            # Add the dot to the displayed set
            displayed_dots.add(dot)

    return square, wedge

# Create the animation
ani = FuncAnimation(fig, update, frames=range(plot_x_limits[0], plot_x_limits[1] - square_config['width']), interval=100, blit=False)

# Show the animation
plt.show()
