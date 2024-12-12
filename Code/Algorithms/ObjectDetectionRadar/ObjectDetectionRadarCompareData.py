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
    
    # Debug: Print resulting frames and point counts
    print("\nFiltered Frames and Point Counts:")
    for frame, data in frames_data.items():
        print(f"Frame {frame}: {len(data[0])} points")
    
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
def create_interactive_plots(frames_data1, frames_data2, x_limits, y_limits, grid_spacing=1, eps=0.5, min_samples=5, history_frames=5):
    """
    Create an interactive plot with two subplots, a slider, and radio buttons,
    including a grid with customizable spacing. Annotates points in ax2 with Doppler values.
    
    Parameters:
        frames_data (dict): The frame data dictionary from `load_data`.
        x_limits (tuple): The x-axis limits as (xmin, xmax).
        y_limits (tuple): The y-axis limits as (ymin, ymax).
        grid_spacing (int): Spacing between grid lines (default is 1).
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
    # Create the figure
    fig = plt.figure(figsize=(14, 14))
    # Define a 2x2 grid layout
    gs = GridSpec(4, 2, figure=fig)

    # Subplots
    ax1 = fig.add_subplot(gs[0, 0])  # Top-left: cumulative data for dataset 1
    ax2 = fig.add_subplot(gs[1, 0])  # Middle-left: per-frame data for dataset 1
    ax3 = fig.add_subplot(gs[0, 1])  # Top-right: cumulative data for dataset 2
    ax4 = fig.add_subplot(gs[1, 1])  # Middle-right: per-frame data for dataset 2
    ax5 = fig.add_subplot(gs[2, 0])  # Bottom-left: occupancy grid for dataset 1
    ax6 = fig.add_subplot(gs[2, 1])  # Bottom-right: occupancy grid for dataset 2
    ax7 = fig.add_subplot(gs[3, 0])  # History-based occupancy grid for dataset 1
    ax8 = fig.add_subplot(gs[3, 1])  # History-based occupancy grid for dataset 2

    # Adjust subplot spacing
    plt.subplots_adjust(left=0.1, bottom=0.2, right=0.9, top=0.9, wspace=0.5, hspace=0.4)

    # Get the custom colormap and normalizer
    cmap, norm = create_custom_colormap()

    print("Custom Colormap Colors:", cmap.colors)
    print("Custom Norm Boundaries:", norm.boundaries)

    # Create lines for ax1
    (line1,) = ax1.plot([], [], 'o', label="Data - Ax1")
    ax1.set_xlim(*x_limits)
    ax1.set_ylim(*y_limits)
    ax1.legend(["Cumulative dots"], loc="upper left")

    # ax2 settings
    ax2.set_xlim(*x_limits)
    ax2.set_ylim(*y_limits)
    ax2.legend(["Dots Per Frame"], loc="upper left")

    # Create lines for ax3
    (line2,) = ax3.plot([], [], 'o', label="Data - Ax3")
    ax3.set_xlim(*x_limits)
    ax3.set_ylim(*y_limits)
    ax3.legend(["Cumulative dots"], loc="upper left")

    # ax4 settings, Cluster plot
    ax4.set_xlim(*x_limits)
    ax4.set_ylim(*y_limits)
    ax4.legend(["Dots Per Frame"], loc="upper left")

    # Create occupancy grid for ax5
    (line5,) = ax5.plot([], [], 'o', label="Data - Ax5")
    ax5.set_xlim(*x_limits)
    ax5.set_ylim(*y_limits)
    ax5.legend(["Cumulative dots"], loc="upper left")

    # Create occupancy grid for ax5
    (line6,) = ax6.plot([], [], 'o', label="Data - Ax6")
    ax6.set_xlim(*x_limits)
    ax6.set_ylim(*y_limits)
    ax6.legend(["Cumulative dots"], loc="upper left")

    # Draw grids and wedges on all axes
    for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8]:
        draw_grid(ax, x_limits, y_limits, grid_spacing)

    # Add slider
    ax_slider1 = plt.axes([0.25, 0.1, 0.65, 0.03])  # [left, bottom, width, height]

    # Update function
    def update(val):
        # Get the current slider value
        slider_value = int(slider1.val)
        
        # Calculate the corresponding frame for each dataset
        max_len = max(len(frames_data1), len(frames_data2))
        frame1 = min(slider_value, len(frames_data1))  # Ensure it doesn't exceed frames_data1
        frame2 = min(slider_value, len(frames_data2))  # Ensure it doesn't exceed frames_data2

        """
        Update Ax1 and Ax3 with cumulative data up to the current frame
        """
        # Ax1: Update cumulative data for dataset 1
        x1, y1 = [], []
        for frame in range(1, frame1 + 1):
            coordinates1, doppler1 = frames_data1.get(frame1, ([], []))
            coordinates2, doppler2 = frames_data2.get(frame2, ([], []))
            if not coordinates1 and not coordinates2:
                print(f"Frame {frame1} has no points after filtering.")
                return
            x1.extend([coord[0] for coord in coordinates1])
            y1.extend([coord[1] for coord in coordinates1])
        line1.set_data(x1, y1)

        # Ax3: Update cumulative data for dataset 2
        x2, y2 = [], []
        for frame in range(1, frame2 + 1):
            coordinates1, doppler1 = frames_data1.get(frame1, ([], []))
            coordinates2, doppler2 = frames_data2.get(frame2, ([], []))
            if not coordinates1 and not coordinates2:
                print(f"Frame {frame1} has no points after filtering.")
                return
            x2.extend([coord[0] for coord in coordinates2])
            y2.extend([coord[1] for coord in coordinates2])
        line2.set_data(x2, y2)

        """
        Update Ax2 and Ax4 with only the current frame's data
        """
        # Ax2: Update current frame data for dataset 1
        ax2.cla()
        ax2.set_xlim(*x_limits)
        ax2.set_ylim(*y_limits)
        draw_grid(ax2, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax2)

        coordinates1, doppler1 = frames_data1.get(frame1, ([], []))
        coordinates2, doppler2 = frames_data2.get(frame2, ([], []))
        if not coordinates1 and not coordinates2:
            print(f"Frame {frame1} has no points after filtering.")
            return
        x2 = [coord[0] for coord in coordinates1]
        y2 = [coord[1] for coord in coordinates1]
        ax2.plot(x2, y2, 'ro')

        for x, y, d in zip(x2, y2, doppler1):
            ax2.text(x, y, f"{d:.2f}", fontsize=8, ha="center", va="bottom", color="blue")
        ax2.set_title(f"Frame {frame1}")
        ax2.legend(["Current Frame"], loc="upper left")

        # Ax4: Update current frame data for dataset 2
        ax4.cla()
        ax4.set_xlim(*x_limits)
        ax4.set_ylim(*y_limits)
        draw_grid(ax4, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax4)

        coordinates1, doppler1 = frames_data1.get(frame1, ([], []))
        coordinates2, doppler2 = frames_data2.get(frame2, ([], []))
        if not coordinates1 and not coordinates2:
            print(f"Frame {frame1} has no points after filtering.")
            return
        x4 = [coord[0] for coord in coordinates2]
        y4 = [coord[1] for coord in coordinates2]
        ax4.plot(x4, y4, 'ro')

        for x, y, d in zip(x4, y4, doppler2):
            ax4.text(x, y, f"{d:.2f}", fontsize=8, ha="center", va="bottom", color="blue")
        ax4.set_title(f"Frame {frame2}")
        ax4.legend(["Current Frame"], loc="upper left")

        """
        Update ax5 and ax6: Occupancy Grids
        """
        # Calculate occupancy grids
        occupancy_grid1 = calculate_occupancy_grid(coordinates1, x_limits, y_limits, grid_spacing)
        occupancy_grid2 = calculate_occupancy_grid(coordinates2, x_limits, y_limits, grid_spacing)

        # Update ax5 for dataset 1
        ax5.cla()
        ax5.imshow(occupancy_grid1.T, extent=(*x_limits, *y_limits), origin='lower', cmap='viridis', aspect='auto')
        ax5.set_title(f"Occupancy Grid - Dataset 1 (Frame {slider_value})")
        ax5.set_xlabel("X [m]")
        ax5.set_ylabel("Y [m]")
        draw_grid(ax5, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax5)

        # Update ax6 for dataset 2
        ax6.cla()
        ax6.imshow(occupancy_grid2.T, extent=(*x_limits, *y_limits), origin='lower', cmap='viridis', aspect='auto')
        ax6.set_title(f"Occupancy Grid - Dataset 2 (Frame {slider_value})")
        ax6.set_xlabel("X [m]")
        ax6.set_ylabel("Y [m]")
        draw_grid(ax6, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax6)

        """
        Update ax7 and ax8: Occupancy Grids
        """
        cumulative_grid1 = calculate_cumulative_occupancy(frames_data1, slider_value, x_limits, y_limits, grid_spacing, history_frames)
        cumulative_grid2 = calculate_cumulative_occupancy(frames_data2, slider_value, x_limits, y_limits, grid_spacing, history_frames)

        ax7.cla()
        ax7.imshow(cumulative_grid1.T, extent=(*x_limits, *y_limits), origin='lower', cmap=cmap, aspect='auto')
        ax7.set_title(f"History Grid - Dataset 1 (Last {history_frames} Frames)")
        ax7.set_xlabel("X [m]")
        ax7.set_ylabel("Y [m]")
        draw_grid(ax7, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax7)

        ax8.cla()
        ax8.imshow(cumulative_grid2.T, extent=(*x_limits, *y_limits), origin='lower', cmap=cmap, aspect='auto')
        ax8.set_title(f"History Grid - Dataset 2 (Last {history_frames} Frames)")
        ax8.set_xlabel("X [m]")
        ax8.set_ylabel("Y [m]")
        draw_grid(ax8, x_limits, y_limits, grid_spacing)
        draw_sensor_area(ax8)

        fig.canvas.draw_idle()

    # Update the slider to cover the maximum range
    max_len = max(len(frames_data1), len(frames_data2))
    slider1 = Slider(ax_slider1, "Frame", min(frames_data1.keys()), max(frames_data1.keys()), valinit=min(frames_data1.keys()), valstep=1)
    slider1.on_changed(update)

    plt.show()


# Example Usage
# Get the absolute path to the CSV file
file_name1 = "coordinates_at1.csv"  # Replace with your file path
script_dir1 = os.path.dirname(os.path.abspath(__file__))
file_path1 = os.path.join(script_dir1, file_name1)

# Get the absolute path to the CSV file
file_name2 = "coordinates_at3.csv"  # Replace with your file path
script_dir2 = os.path.dirname(os.path.abspath(__file__))
file_path2 = os.path.join(script_dir2, file_name2)

y_threshold = 0.0  # Disregard points with Y < num
z_threshold = (-0.30, 3.0)
doppler_threshold = 0.1 # Disregard points with doppler < num

frames_data1 = load_data(file_path1, y_threshold, z_threshold, doppler_threshold)
frames_data2 = load_data(file_path2, y_threshold, z_threshold, doppler_threshold)

"""
Having a legen of Cluster -1, means no cluster has been created
Same as having Grey Clusters
"""
create_interactive_plots(frames_data1, frames_data2, x_limits=(-8, 8), y_limits=(0, 15), eps=0.4, min_samples=5, history_frames = 5)