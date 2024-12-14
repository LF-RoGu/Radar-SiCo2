import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, RadioButtons
from matplotlib.patches import Wedge
from matplotlib.gridspec import GridSpec
from matplotlib.colors import ListedColormap, BoundaryNorm

# Utility function to load data
def load_data(file_name, y_threshold=None, z_threshold=None, doppler_threshold=None):
    """
    Load CSV data from the specified file and organize it by frame, filtering out rows where
    any value violates the thresholds.

    Parameters:
        file_name (str): Path to the CSV file.
        y_threshold (float, optional): Minimum Y-value to include points. Points with Y < y_threshold
                                       will be excluded. Defaults to None (no filtering).
        z_threshold (tuple, optional): Tuple (lower_bound, upper_bound) for filtering Z values.
                                       Defaults to None (no filtering).
        doppler_threshold (float, optional): Minimum absolute Doppler value to include points. Points with
                                             abs(Doppler) <= doppler_threshold will be excluded. Defaults to None (no filtering).
    
    Returns:
        dict: A dictionary where each key is a frame number, and the value is a tuple:
              (coordinates, doppler), where:
              - coordinates: List of tuples (x, y, z) for each point in the frame.
              - doppler: List of Doppler values for each point in the frame.
    """
    if not os.path.exists(file_name):
        raise FileNotFoundError(f"Error: File not found at {file_name}")
    
    # Load the CSV data
    df = pd.read_csv(file_name)
    
    # Debug: Print initial data size
    print(f"Initial data size: {df.shape}")
    
    # Apply filtering: Remove rows where any condition fails
    if y_threshold is not None:
        df = df[df["Y [m]"] >= y_threshold]
        print(f"Filtered data size (Y [m] >= {y_threshold}): {df.shape}")

    if z_threshold is not None:
        # Ensure z_threshold is a tuple with lower and upper bounds
        if isinstance(z_threshold, tuple) and len(z_threshold) == 2:
            lower_bound, upper_bound = z_threshold
            df = df[(df["Z [m]"] >= lower_bound) & (df["Z [m]"] <= upper_bound)]
            print(f"Filtered data size ({lower_bound} <= Z [m] <= {upper_bound}): {df.shape}")
        else:
            raise ValueError("z_threshold must be a tuple with two elements: (lower_bound, upper_bound).")

    if doppler_threshold is not None:
        df = df[df["Doppler [m/s]"].abs() > doppler_threshold]
        print(f"Filtered data size (Doppler [m/s] > {doppler_threshold}): {df.shape}")
    
    # Handle empty dataset case
    if df.empty:
        print(f"Warning: No data points remain after applying filters.")
        return {}
    
    # Group data by frame and organize the output
    frames_data = {}
    for frame, group in df.groupby("Frame"):
        coordinates = list(zip(group["X [m]"], group["Y [m]"], group["Z [m]"]))
        doppler = group["Doppler [m/s]"].tolist()
        if coordinates:  # Ensure frames with no points are skipped
            frames_data[frame] = (coordinates, doppler)
    
    return frames_data



# Function to draw the sensor's detection area as a wedge
def draw_sensor_area(ax, sensor_origin=(0, -1), azimuth=60, max_distance=12):
    """
    Draw a wedge to simulate the sensor's detection area pointing upwards.

    Parameters:
        ax (matplotlib.axes._subplots.AxesSubplot): The matplotlib axis to draw on.
        sensor_origin (tuple): The (x, y) coordinates of the sensor's origin.
        azimuth (float): The azimuth angle (in degrees) for the sensor's field of view.
        max_distance (float): The maximum detection radius of the sensor.

    Returns:
        None
    """
    # Adjust the angles so the wedge points upwards (positive Y-axis)
    start_angle = 90 - azimuth / 2
    end_angle = 90 + azimuth / 2

    # Create the wedge
    wedge = Wedge(
        center=sensor_origin,
        r=max_distance,
        theta1=start_angle,
        theta2=end_angle,
        facecolor="blue",
        alpha=0.2,
        edgecolor="black",
        linewidth=1
    )

    # Add the wedge to the axis
    ax.add_patch(wedge)

    # Optionally, add the sensor's location as a point
    ax.scatter(*sensor_origin, color="green", label="Sensor Location")

def calculate_occupancy_grid(points, x_limits, y_limits, grid_spacing):
    """
    Calculate an occupancy grid for the given points.

    Parameters:
        points (list of tuples): List of (x, y, z) coordinates.
        x_limits (tuple): The x-axis limits as (xmin, xmax).
        y_limits (tuple): The y-axis limits as (ymin, ymax).
        grid_spacing (int): Spacing between grid cells.

    Returns:
        np.ndarray: 2D occupancy grid.
    """
    # Calculate grid size
    x_bins = int((x_limits[1] - x_limits[0]) / grid_spacing)
    y_bins = int((y_limits[1] - y_limits[0]) / grid_spacing)

    # Initialize the grid
    occupancy_grid = np.zeros((x_bins, y_bins))

    # Populate the grid
    for x, y, _ in points:
        if x_limits[0] <= x < x_limits[1] and y_limits[0] <= y < y_limits[1]:
            x_idx = int((x - x_limits[0]) / grid_spacing)
            y_idx = int((y - y_limits[0]) / grid_spacing)
            occupancy_grid[x_idx, y_idx] += 1

    return occupancy_grid

# Plotting function
def create_interactive_plots(frames_data1, x_limits, y_limits, grid_spacing=1, eps=0.5, min_samples=5, history_frames=5):
    """
    Create an interactive plot with two subplots, a slider, and radio buttons,
    including a grid with customizable spacing. Annotates points in ax2 with Doppler values.
    
    Parameters:
        frames_data1 (dict): Data for dataset 1.
        frames_data2 (dict): Data for dataset 2.
        frames_data3 (dict): Data for dataset 3.
        x_limits (tuple): The x-axis limits as (xmin, xmax).
        y_limits (tuple): The y-axis limits as (ymin, ymax).
        grid_spacing (int): Spacing between grid lines (default is 1).
        history_frames (int): Number of frames for history-based visualization.
    """

    # Helper function to draw the grid with specified spacing
    def draw_grid(ax, x_limits, y_limits, grid_spacing):
        x_ticks = range(int(np.floor(x_limits[0])), int(np.ceil(x_limits[1])) + 1, grid_spacing)
        y_ticks = range(int(np.floor(y_limits[0])), int(np.ceil(y_limits[1])) + 1, grid_spacing)
        for x in x_ticks:
            ax.plot([x, x], y_limits, linestyle='--', color='gray', linewidth=0.5)
        for y in y_ticks:
            ax.plot(x_limits, [y, y], linestyle='--', color='gray', linewidth=0.5)
    # Helper function to calculate cumulative occupancy over history
    def calculate_cumulative_occupancy(frames_data, frame_idx, x_limits, y_limits, grid_spacing, history_frames):
        """
        Calculate a cumulative occupancy grid over the last `history_frames` frames.

        Parameters:
            frames_data (dict): Frame data dictionary.
            frame_idx (int): Current frame index.
            x_limits (tuple): X-axis limits.
            y_limits (tuple): Y-axis limits.
            grid_spacing (int): Spacing between grid cells.
            history_frames (int): Number of frames to include in the history.

        Returns:
            np.ndarray: Cumulative occupancy grid.
        """
        cumulative_grid = np.zeros((int((x_limits[1] - x_limits[0]) / grid_spacing),
                                    int((y_limits[1] - y_limits[0]) / grid_spacing)))

        for i in range(max(1, frame_idx - history_frames + 1), frame_idx + 1):
            coordinates, _ = frames_data.get(i, ([], []))
            occupancy_grid = calculate_occupancy_grid(coordinates, x_limits, y_limits, grid_spacing)
            cumulative_grid += occupancy_grid

        # Normalize cumulative grid to [0, 1] (optional for visualization purposes)
        cumulative_grid = np.clip(cumulative_grid, 0, 10)  # Limit max values to 10
        return cumulative_grid
    # Helper function 
    def create_custom_colormap():
        """
        Create a custom colormap for the occupancy grid.
        Returns:
            cmap: Custom colormap with a specific background color.
            norm: Normalizer to map data values to colormap levels.
        """
        # Define colors: First is the background color, followed by density colors
        colors = [
            "white",      # Background color (e.g., for 0)
            "#d1e5f0",    # Light blue (low density)
            "#92c5de",    # Blue
            "#4393c3",    # Medium density
            "#2166ac",    # Dark blue (high density)
            "#053061"     # Very high density
        ]
        cmap = ListedColormap(colors)

        # Define boundaries for each color bin
        boundaries = [0, 1, 2, 3, 4, 5, np.inf]  # Bins for densities
        norm = BoundaryNorm(boundaries, cmap.N, clip=True)

        return cmap, norm

    # Create the figure and subplots
    fig = plt.figure(figsize=(18, 14))
    # Define a 4x1 grid layout
    gs = GridSpec(4, 1, figure=fig)

    # Subplots
    # Dataset 1
    ax1_1 = fig.add_subplot(gs[0, 0])  # Top-left: cumulative data for dataset 1
    ax1_2 = fig.add_subplot(gs[1, 0])  # Middle-left: per-frame data for dataset 1
    ax1_3 = fig.add_subplot(gs[2, 0])  # Bottom-left: occupancy grid for dataset 1
    ax1_4 = fig.add_subplot(gs[3, 0])  # History-based occupancy grid for dataset 1

    # Adjust subplot spacing
    plt.subplots_adjust(left=0.1, bottom=0.2, right=0.9, top=0.9, wspace=0.5, hspace=0.6)

    # Apply grid to all subplots
    for ax in [ax1_1, ax1_2, ax1_3, ax1_4]:
        draw_grid(ax, x_limits, y_limits, grid_spacing)

    # Get the custom colormap and normalizer
    cmap, norm = create_custom_colormap()

    # Initialize cumulative plots
    (line1_1,) = ax1_1.plot([], [], 'o', label="Dataset 1: Cumulative Data")

    for ax, title in zip([ax1_1], ["Dataset 1"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.legend(loc="upper left")
        ax.set_title(f"{title} - Cumulative Data")

    # Initialize per-frame plots
    for ax, title in zip([ax1_2], ["Dataset 1"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.legend(["Dots Per Frame"], loc="upper left")
        ax.set_title(f"{title} - Per Frame Data")

    # Initialize occupancy grids
    for ax, title in zip([ax1_3], ["Dataset 1"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.set_title(f"{title} - Occupancy Grid")

    # Initialize history-based grids
    for ax, title in zip([ax1_4], ["Dataset 1"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.set_title(f"{title} - History-Based Grid")

    # Update function
    def update(val):
        # Get the current slider value
        frame1 = int(slider1.val)

        """
        Dataset 1
        """
        coordinates1, doppler1 = frames_data1.get(frame1, ([], []))  # Current frame's data
        if not coordinates1:
            print(f"Frame {frame1} for Dataset 1 has no points after filtering.")
            return
        
        # Ax1_1: Update cumulative data for dataset 1
        x1, y1 = [], []
        for frame in range(1, frame1 + 1):  # Accumulate data up to the current frame
            x1.extend([coord[0] for coord in coordinates1])
            y1.extend([coord[1] for coord in coordinates1])

        line1_1.set_data(x1, y1)
        ax1_1.set_xlabel("X [m]")
        ax1_1.set_ylabel("Y [m]")

        # Ax1_2: Update current frame data for dataset 1
        ax1_2.cla()
        ax1_2.set_xlim(*x_limits)
        ax1_2.set_ylim(*y_limits)
        draw_grid(ax1_2, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax1_2)  # Assuming this function visualizes the sensor's area

        x1 = [coord[0] for coord in coordinates1]
        y1 = [coord[1] for coord in coordinates1]
        ax1_2.plot(x1, y1, 'ro')

        # Annotate Doppler values on the plot
        for x, y, d in zip(x1, y1, doppler1):
            ax1_2.text(x, y, f"{d:.2f}", fontsize=8, ha="center", va="bottom", color="blue")

        ax1_2.set_title(f"Frame {frame1} - Dataset 1")
        ax1_2.legend(["Current Frame"], loc="upper left")
        ax1_2.set_xlabel("X [m]")
        ax1_2.set_ylabel("Y [m]")

        # Update ax1_3: Occupancy Grid for Dataset 1
        occupancy_grid1 = calculate_occupancy_grid(coordinates1, x_limits, y_limits, grid_spacing)
        ax1_3.cla()
        ax1_3.imshow(occupancy_grid1.T, extent=(*x_limits, *y_limits), origin='lower', cmap=cmap, aspect='auto')
        ax1_3.set_title(f"Occupancy Grid - Dataset 1 (Frame {frame1})")
        ax1_3.set_xlabel("X [m]")
        ax1_3.set_ylabel("Y [m]")
        draw_grid(ax1_3, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax1_3)

        # Update ax1_4: History-Based Occupancy Grid for Dataset 1
        cumulative_grid1 = calculate_cumulative_occupancy(
            frames_data1, frame1, x_limits, y_limits, grid_spacing, history_frames
        )
        ax1_4.cla()
        ax1_4.imshow(cumulative_grid1.T, extent=(*x_limits, *y_limits), origin='lower', cmap=cmap, aspect='auto')
        ax1_4.set_title(f"History Grid - Dataset 1 (Last {history_frames} Frames)")
        ax1_4.set_xlabel("X [m]")
        ax1_4.set_ylabel("Y [m]")
        draw_grid(ax1_4, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax1_4)

        fig.canvas.draw_idle()
    # Add slider
    # [left, bottom, width, height]
    ax_slider1 = plt.axes([0.25, 0.10, 0.65, 0.03])  # Slider for Dataset 1
    # Initialize sliders with respective frame ranges
    slider1 = Slider(
        ax_slider1, 
        "Frame 1", 
        min(frames_data1.keys()), 
        max(frames_data1.keys()), 
        valinit=min(frames_data1.keys()), 
        valstep=1
    )

    slider1.on_changed(update)

    plt.show()


# Example Usage
# Get the absolute path to the CSV file
file_name1 = "coordinates_sl_at1.csv"  # Replace with your file path
script_dir1 = os.path.dirname(os.path.abspath(__file__))
file_path1 = os.path.join(script_dir1, file_name1)

y_threshold = 0.0  # Disregard points with Y < num
z_threshold = (-0.30, 3.0)
doppler_threshold = 0.0 # Disregard points with doppler < num

frames_data1 = load_data(file_path1, y_threshold, z_threshold, doppler_threshold)

"""
Having a legen of Cluster -1, means no cluster has been created
Same as having Grey Clusters
"""
create_interactive_plots(frames_data1, x_limits=(-8, 8), y_limits=(0, 15), eps=0.4, min_samples=5, history_frames = 10)