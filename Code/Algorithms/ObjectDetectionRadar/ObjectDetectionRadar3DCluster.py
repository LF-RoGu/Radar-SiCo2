import os
import pandas as pd
import numpy as np
import struct
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.patches import Wedge
from matplotlib.gridspec import GridSpec
from matplotlib.colors import ListedColormap, BoundaryNorm
from mpl_toolkits.mplot3d import Axes3D


from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

# Parse Frame Header
def parse_frame_header(raw_data):
    if len(raw_data) < 40:
        raise ValueError("Insufficient data for Frame Header")
    raw_bytes = bytes([raw_data.pop(0) for _ in range(40)])
    frame_header = struct.unpack('<QIIIIIIII', raw_bytes)
    return {
        "Magic Word": f"0x{frame_header[0]:016X}",
        "Version": f"0x{frame_header[1]:08X}",
        "Total Packet Length": frame_header[2],
        "Platform": f"0x{frame_header[3]:08X}",
        "Frame Number": frame_header[4],
        "Time [in CPU Cycles]": frame_header[5],
        "Num Detected Obj": frame_header[6],
        "Num TLVs": frame_header[7],
        "Subframe Number": frame_header[8]
    }

# Parse TLV Header
def parse_tlv_header(raw_data):
    if len(raw_data) < 8:
        raise ValueError("Insufficient data for TLV Header")
    raw_bytes = bytes([raw_data.pop(0) for _ in range(8)])
    tlv_type, tlv_length = struct.unpack('<II', raw_bytes)
    return {"TLV Type": tlv_type, "TLV Length": tlv_length}

# Parse TLV Payload
def parse_tlv_payload(tlv_header, raw_data):
    tlv_type = tlv_header["TLV Type"]
    payload_length = tlv_header["TLV Length"]
    payload = [raw_data.pop(0) for _ in range(payload_length)]

    # Detected Points Example
    if tlv_type == 1:  # Detected Points
        point_size = 16
        detected_points = []
        for i in range(payload_length // point_size):
            point_bytes = bytes(payload[i * point_size:(i + 1) * point_size])
            x, y, z, doppler = struct.unpack('<ffff', point_bytes)
            detected_points.append({"X [m]": x, "Y [m]": y, "Z [m]": z, "Doppler [m/s]": doppler})
        return {"Detected Points": detected_points}
    return None

# Process the CSV file and parse data
def process_log_file(file_path):
    """
    Parses the log file and returns all frames and detected points as a dictionary.
    
    Returns:
        dict: A dictionary containing frame headers and their respective detected points.
    """
    frames_dict = {}  # Dictionary to hold all parsed frame data

    # Load the CSV data, skip the header row
    data = pd.read_csv(file_path, names=["Timestamp", "RawData"], skiprows=1)

    for row_idx in range(len(data)):
        try:
            # Skip invalid rows
            if pd.isnull(data.iloc[row_idx]['RawData']):
                print(f"Skipping row {row_idx + 1}: Invalid or null data.")
                continue

            # Convert raw data to a list of integers
            raw_data_list = [int(x) for x in data.iloc[row_idx]['RawData'].split(',')]

            # Parse the Frame Header
            frame_header = parse_frame_header(raw_data_list)
            num_tlvs = frame_header["Num TLVs"]
            frame_number = frame_header["Frame Number"]
            #print(f"Parsing Frame {frame_number}: {frame_header}")

            # Initialize the frame entry
            frames_dict[frame_number] = {
                "Frame Header": frame_header,
                "Detected Points": []
            }

            # Parse TLVs
            for _ in range(num_tlvs):
                if len(raw_data_list) < 8:
                    print(f"Skipping incomplete TLV data in Frame {frame_number}")
                    break
                
                tlv_header = parse_tlv_header(raw_data_list)

                # Only process Detected Points (TLV Type 1)
                if tlv_header["TLV Type"] == 1:
                    tlv_payload = parse_tlv_payload(tlv_header, raw_data_list)
                    if tlv_payload and "Detected Points" in tlv_payload:
                        frames_dict[frame_number]["Detected Points"].extend(tlv_payload["Detected Points"])

        except (ValueError, IndexError) as e:
            print(f"Error parsing row {row_idx + 1}: {e}")

    return frames_dict

# Create a new dictionary with frame numbers and coordinates + Doppler speed
def extract_coordinates_with_doppler(frames_data, y_threshold=None, z_threshold=None, doppler_threshold=None):
    coordinates_dict = {}

    for frame_num, frame_content in frames_data.items():
        # Extract detected points for the current frame
        points = frame_content["Detected Points"]

        # Create a list of dictionaries with required fields and filters
        coordinates = []
        for point in points:
            # Apply threshold filters
            if y_threshold is not None and point["Y [m]"] < y_threshold:
                continue  # Skip if Y is below the threshold
            
            if z_threshold is not None and not (z_threshold[0] <= point["Z [m]"] <= z_threshold[1]):
                continue  # Skip if Z is outside the range
            
            if doppler_threshold is not None and abs(point["Doppler [m/s]"]) <= doppler_threshold:
                continue  # Skip if Doppler speed is below the threshold

            # Add the point to the list if it passes all filters
            coordinates.append({
                "X [m]": point["X [m]"],
                "Y [m]": point["Y [m]"],
                "Z [m]": point["Z [m]"],
                "Doppler [m/s]": point["Doppler [m/s]"]
            })
        
        # Add the filtered coordinates list to the dictionary
        if coordinates:  # Only add frames with valid points
            coordinates_dict[frame_num] = coordinates

    return coordinates_dict

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

def draw_sensor_area_3d(ax, z_plane=0.30):
    """
    Draw the sensor area (e.g., a circle) on a fixed Z-plane in a 3D plot.

    Args:
    - ax: Matplotlib 3D axis.
    - z_plane (float): Fixed Z-coordinate for the sensor area.
    """
    sensor_radius = 1.0  # Example radius for the sensor
    theta = np.linspace(0, 2 * np.pi, 100)
    x_circle = sensor_radius * np.cos(theta)
    y_circle = sensor_radius * np.sin(theta)
    ax.plot(x_circle, y_circle, zs=z_plane, color='red', linewidth=1.5, label="Sensor Area")

def calculate_occupancy_grid(points, x_limits, y_limits, grid_spacing):
    """
    Calculate an occupancy grid for the given points.

    Parameters:
        points (list of tuples): List of (x, y) or (x, y, z) coordinates.
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
    for point in points:
        if len(point) == 3:
            x, y, _ = point  # Unpack x, y, z
        elif len(point) == 2:
            x, y = point  # Unpack x, y only
        else:
            raise ValueError(f"Point format not supported: {point}")

        if x_limits[0] <= x < x_limits[1] and y_limits[0] <= y < y_limits[1]:
            x_idx = int((x - x_limits[0]) / grid_spacing)
            y_idx = int((y - y_limits[0]) / grid_spacing)
            occupancy_grid[x_idx, y_idx] += 1

    return occupancy_grid

def dbscan_clustering(data, eps=1.0, min_samples=3):
    """
    Perform DBSCAN clustering on the X, Y, and Z coordinates.

    Args:
    - data (list or DataFrame): Data containing X, Y, and Z coordinates.
    - eps (float): The maximum distance between two samples for one to be considered in the neighborhood.
    - min_samples (int): The number of samples in a neighborhood for a point to be considered a core point.

    Returns:
    - labels (array): Cluster labels for each point. Noise points are labeled as -1.
    """
    # Convert input data to numpy array if it's a list
    if isinstance(data, list):
        if not data:  # Handle empty list
            print("DBSCAN: No data points provided.")
            return np.array([])  # Return empty labels
        data = np.array(data)

    # Ensure the data contains valid 3D points
    if data.shape[0] == 0 or data.shape[1] != 3:
        print("DBSCAN: Data must contain 3D points (X, Y, Z).")
        return np.array([])

    # Perform DBSCAN clustering
    db = DBSCAN(eps=eps, min_samples=min_samples).fit(data)
    return db.labels_

# Plotting function
def create_interactive_plots(frames_data, x_limits, y_limits, grid_spacing=1, eps1=0.5, min_samples1=5, eps2=0.5, min_samples2=5, history_frames=5):
    """
    Create an interactive plot with two subplots, a slider, and radio buttons,
    including a grid with customizable spacing. Annotates points in ax2 with Doppler values.
    
    Parameters:
        frames_data (dict): Data for dataset.
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
    def draw_grid_3d(ax, x_limits, y_limits, grid_spacing, z_plane=0):
        """
        Draw a 2D grid at a fixed Z-plane on a 3D plot.

        Args:
        - ax: Matplotlib 3D axis.
        - x_limits (tuple): X-axis limits as (xmin, xmax).
        - y_limits (tuple): Y-axis limits as (ymin, ymax).
        - grid_spacing (float): Spacing between grid lines.
        - z_plane (float): Fixed Z-coordinate for the grid.
        """
        x_range = np.arange(x_limits[0], x_limits[1] + grid_spacing, grid_spacing)
        y_range = np.arange(y_limits[0], y_limits[1] + grid_spacing, grid_spacing)

        # Draw grid lines parallel to X-axis
        for y in y_range:
            ax.plot([x_limits[0], x_limits[1]], [y, y], zs=z_plane, color='gray', linestyle='--', linewidth=0.5)

        # Draw grid lines parallel to Y-axis
        for x in x_range:
            ax.plot([x, x], [y_limits[0], y_limits[1]], zs=z_plane, color='gray', linestyle='--', linewidth=0.5)

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
            coordinates = frames_data.get(i, [])  # Retrieve the list of points
            # Extract X and Y coordinates as tuples
            points = [(point["X [m]"], point["Y [m]"]) for point in coordinates]
            # Update the cumulative grid
            occupancy_grid = calculate_occupancy_grid(points, x_limits, y_limits, grid_spacing)
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

    # Create a larger figure to accommodate bigger 3D plots
    fig = plt.figure(figsize=(24, 18))  # Larger figure size

    # Define a 2x3 grid layout with custom width ratios
    gs = GridSpec(2, 3, figure=fig, width_ratios=[1, 1, 1], height_ratios=[1, 1])

    # Expand the 3D plots over multiple rows
    # Dataset 1 subplots (Cumulative and Current Frame)
    ax1_1 = fig.add_subplot(gs[0, 0], projection='3d')  # Spanning first two rows in column 0
    ax1_2 = fig.add_subplot(gs[1, 0], projection='3d')  # Spanning last two rows in column 0

    # Dataset 2 subplots (Cumulative Clusters and Current Clusters)
    ax2_1 = fig.add_subplot(gs[0, 1], projection='3d')  # Spanning first two rows in column 1
    ax2_2 = fig.add_subplot(gs[1, 1], projection='3d')  # Spanning last two rows in column 1

    # Dataset 3 subplots (Cumulative Clusters and Current Clusters)
    ax3_1 = fig.add_subplot(gs[0, 2], projection='3d')  # Spanning first two rows in column 1
    ax3_2 = fig.add_subplot(gs[1, 2], projection='3d')  # Spanning last two rows in column 1

    elev = 90
    azim = 90
    # Set the initial 3D view orientation
    ax1_1.view_init(elev=elev, azim=azim)
    ax1_2.view_init(elev=elev, azim=azim)
    ax2_1.view_init(elev=elev, azim=azim)
    ax2_2.view_init(elev=elev, azim=azim)
    ax3_1.view_init(elev=elev, azim=azim)
    ax3_2.view_init(elev=elev, azim=azim)

    # Adjust subplot spacing
    plt.subplots_adjust(left=0.1, bottom=0.2, right=0.9, top=0.9, wspace=0.5, hspace=0.6)

    # Apply grid to all subplots
    for ax in [ax1_1, ax1_2, ax2_1, ax2_2, ax3_1, ax3_2]:
        draw_grid(ax, x_limits, y_limits, grid_spacing)

    for ax, title in zip([ax1_1], ["Point Cloud"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.set_title(f"{title} - Cumulative Data")

    # Initialize per-frame plots
    for ax, title in zip([ax1_2], ["Point Cloud"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.legend(["Dots Per Frame"], loc="upper left")
        ax.set_title(f"{title} - Per Frame Data")

    for ax, title in zip([ax2_1], ["DBSCAN applied"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        #ax.legend(loc="upper left")
        ax.set_title(f"{title} - Cumulative Data")

    # Initialize per-frame plots
    for ax, title in zip([ax2_2], ["DBSCAN applied"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.legend(["Dots Per Frame"], loc="upper left")
        ax.set_title(f"{title} - Per Frame Data")

    for ax, title in zip([ax3_1], ["DBSCAN2 applied"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        #ax.legend(loc="upper left")
        ax.set_title(f"{title} - Cumulative Data")

    # Initialize per-frame plots
    for ax, title in zip([ax3_2], ["DBSCAN2 applied"]):
        ax.set_xlim(*x_limits)
        ax.set_ylim(*y_limits)
        ax.legend(["Dots Per Frame"], loc="upper left")
        ax.set_title(f"{title} - Per Frame Data")

    # Update function
    def update(val):
        # Get the current slider value
        frame_idx = int(slider_idx.val)

        """
        Dataset 1
        """
        # Initialize lists to store X, Y coordinates and Doppler values for the current frame
        coordinates1 = []

        # Get the list of points for the current frame
        current_frame_points = frames_data.get(frame_idx, [])

        # Extract X, Y coordinates and Doppler values
        for point in current_frame_points:
            x_coord = point["X [m]"]
            y_coord = point["Y [m]"]
            z_coord = point["Y [m]"]
            #doppler_speed = point["Doppler [m/s]"]

            coordinates1.append((x_coord, y_coord, z_coord))
            #doppler1.append(doppler_speed)

        # Check if the current frame has no valid points
        if not coordinates1:
            print(f"Frame {frame_idx} for Dataset 1 has no points after filtering.")
            return

        # -----------------------------------------
        # Ax1_1: Update cumulative data for dataset 1
        # -----------------------------------------
        x1, y1, z1 = [], [], []
        # Accumulate historical data
        for frame in range(1, frame_idx + 1):
            points = frames_data.get(frame, [])
            for point in points:
                x1.append(point["X [m]"])
                y1.append(point["Y [m]"])
                z1.append(point["Z [m]"])

        # Plot cumulative data in 3D
        ax1_1.cla()
        ax1_1.scatter3D(x1, y1, z1, c='blue', label="Cumulative Data")
        ax1_1.set_xlabel("X [m]")
        ax1_1.set_ylabel("Y [m]")
        ax1_1.set_zlabel("Z [m]")
        ax1_1.set_title("Cumulative Data (3D)")
        # Draw 2D grid and sensor area at Z=0
        draw_grid_3d(ax1_1, x_limits, y_limits, grid_spacing, z_plane=0)
        draw_sensor_area_3d(ax1_1)

        # -----------------------------------------
        # Ax1_2: Update current frame data for dataset 1
        # -----------------------------------------
        # Extract X, Y, and Z coordinates for the current frame
        x2 = [point[0] for point in coordinates1]
        y2 = [point[1] for point in coordinates1]
        z2 = [point["Z [m]"] for point in current_frame_points]

        # Plot current frame points in 3D
        ax1_2.cla()
        ax1_2.scatter3D(z2, y2, z2, c='red', label="Current Frame")
        ax1_2.set_xlabel("X [m]")
        ax1_2.set_ylabel("Y [m]")
        ax1_2.set_zlabel("Z [m]")
        ax1_2.set_title(f"Frame {frame_idx} - Current Frame (3D)")
        # Draw 2D grid and sensor area at Z=0
        draw_grid_3d(ax1_2, x_limits, y_limits, grid_spacing, z_plane=0)
        draw_sensor_area_3d(ax1_2)

        """
        Dataset 2 (with DBSCAN clustering)
        """

        # Initialize lists to store X, Y, and Z coordinates
        coordinates2 = []

        # Get the list of points for the current frame
        current_frame_points = frames_data.get(frame_idx, [])

        # Extract X, Y, and Z coordinates for clustering
        for point in current_frame_points:
            x_coord = point["X [m]"]
            y_coord = point["Y [m]"]
            z_coord = point["Z [m]"]
            coordinates2.append([x_coord, y_coord, z_coord])

        # Check if the current frame has no valid points
        if not coordinates2:
            print(f"Frame {frame_idx} for Dataset 2 has no points after filtering.")
            return

        # Prepare DataFrame for clustering
        # Prepare DataFrame for clustering
        cluster = pd.DataFrame(coordinates2, columns=["X [m]", "Y [m]", "Z [m]"])
        cluster["Cluster1"] = dbscan_clustering(cluster, eps=eps1, min_samples=min_samples1)

        # -----------------------------------------
        # Ax2_1: Cumulative clusters for Dataset 2
        # -----------------------------------------
        #ax2_1.cla()
        if not hasattr(update, "cumulative_clusters"):
            update.cumulative_clusters = {"x": [], "y": [], "z": []}

        for cluster_label in set(cluster["Cluster1"]):
            if cluster_label == -1:  # Skip noise points
                continue
            # Extract points for the current cluster
            cluster_points = cluster[cluster["Cluster1"] == cluster_label][["X [m]", "Y [m]", "Z [m]"]].values
            update.cumulative_clusters["x"].extend(cluster_points[:, 0])
            update.cumulative_clusters["y"].extend(cluster_points[:, 1])
            update.cumulative_clusters["z"].extend(cluster_points[:, 2])

        # Plot cumulative clusters
        ax2_1.scatter3D(update.cumulative_clusters["x"], update.cumulative_clusters["y"], update.cumulative_clusters["z"],
                        c='purple', alpha=0.5, label="Cumulative Clusters")
        ax2_1.set_xlabel("X [m]")
        ax2_1.set_ylabel("Y [m]")
        ax2_1.set_zlabel("Z [m]")
        ax2_1.set_title("Cumulative Clusters (3D)")
        draw_grid_3d(ax2_1, x_limits, y_limits, grid_spacing, z_plane=0)
        draw_sensor_area_3d(ax2_1)

        # -----------------------------------------
        # Ax2_2: Current frame clusters for Dataset 2
        # -----------------------------------------
        ax2_2.cla()
        unique_labels = set(cluster["Cluster1"])
        colors = [plt.cm.Spectral(each) for each in np.linspace(0, 1, len(unique_labels))]

        for cluster_label, col in zip(unique_labels, colors):
            if cluster_label == -1:  # Noise points
                col = [0, 0, 0, 1]  # Black for noise
            else:
                # Extract points for the current cluster
                cluster_points = cluster[cluster["Cluster1"] == cluster_label][["X [m]", "Y [m]", "Z [m]"]].values
                ax2_2.scatter3D(cluster_points[:, 0], cluster_points[:, 1], cluster_points[:, 2],
                                c=[col], label=f"Cluster {cluster_label}")

        ax2_2.set_xlabel("X [m]")
        ax2_2.set_ylabel("Y [m]")
        ax2_2.set_zlabel("Z [m]")
        ax2_2.set_title(f"Frame {frame_idx} - Current Frame Clusters (3D)")
        draw_grid_3d(ax2_2, x_limits, y_limits, grid_spacing, z_plane=0)
        draw_sensor_area_3d(ax2_2)

        """
        Dataset 3 (with Second-Level DBSCAN clustering)
        """
        eps2 = 0.4
        min_samples2 = 2

        # Get the list of clustered points from Dataset 2
        coordinates3 = []
        for cluster_label in set(cluster["Cluster1"]):
            if cluster_label == -1:  # Skip noise points
                continue
            # Extract points belonging to this first-level cluster
            cluster_points = cluster.loc[cluster["Cluster1"] == cluster_label, ["X [m]", "Y [m]", "Z [m]"]].values
            coordinates3.extend(cluster_points)

        # Check if there are no valid points
        if not coordinates3:
            print(f"Frame {frame_idx} for Dataset 3 has no points after filtering.")
            return

        # Apply second-level DBSCAN clustering
        df3 = pd.DataFrame(coordinates3, columns=["X [m]", "Y [m]", "Z [m]"])
        df3["Cluster2"] = dbscan_clustering(df3, eps=eps2, min_samples=min_samples2)

        # -----------------------------------------
        # Ax3_1: Update cumulative clusters
        # -----------------------------------------
        #ax3_1.cla()
        for cluster_label in set(df3["Cluster2"]):
            if cluster_label == -1:  # Noise points
                continue
            cluster_points = df3[df3["Cluster2"] == cluster_label]
            ax3_1.scatter3D(cluster_points["X [m]"], cluster_points["Y [m]"], cluster_points["Z [m]"],
                            label=f"Cluster {cluster_label}", alpha=0.6)
        ax3_1.set_xlabel("X [m]")
        ax3_1.set_ylabel("Y [m]")
        ax3_1.set_zlabel("Z [m]")
        ax3_1.set_title("Second-Level Clustering (Cumulative)")
        draw_grid_3d(ax3_1, x_limits, y_limits, grid_spacing, z_plane=0)
        draw_sensor_area_3d(ax3_1)

        # -----------------------------------------
        # Ax3_2: Current frame second-level clusters
        # -----------------------------------------
        ax3_2.cla()
        for cluster_label in set(df3["Cluster2"]):
            if cluster_label == -1:  # Noise points
                col = [0, 0, 0, 1]  # Black for noise
            else:
                cluster_points = df3[df3["Cluster2"] == cluster_label]
                ax3_2.scatter3D(cluster_points["X [m]"], cluster_points["Y [m]"], cluster_points["Z [m]"],
                                label=f"Cluster {cluster_label}")
        ax3_2.set_xlabel("X [m]")
        ax3_2.set_ylabel("Y [m]")
        ax3_2.set_zlabel("Z [m]")
        ax3_2.set_title(f"Second-Level Clustering - Frame {frame_idx}")
        draw_grid_3d(ax3_2, x_limits, y_limits, grid_spacing, z_plane=0)
        draw_sensor_area_3d(ax3_2)



        fig.canvas.draw_idle()
    # Add slider
    # [left, bottom, width, height]
    ax_slider = plt.axes([0.25, 0.10, 0.65, 0.03])  # Slider for Dataset 1
    # Initialize sliders with respective frame ranges
    slider_idx = Slider(
        ax_slider, 
        "Column 1", 
        min(frames_data.keys()), 
        max(frames_data.keys()), 
        valinit=min(frames_data.keys()), 
        valstep=1
    )

    slider_idx.on_changed(update)

    plt.show()


# Example Usage
# Get the absolute path to the CSV file
script_dir = os.path.dirname(os.path.abspath(__file__))
relative_path = os.path.join("..", "..", "..", "Logs", "LogsPart3", "DynamicMonitoring", "Test_30fps_dist15mts_vehicleLog_5mps_3x3Wall_drivearound_att6_log.csv")
file_path = os.path.normpath(os.path.join(script_dir, relative_path))

y_threshold = 1.0  # Disregard points with Y < num
z_threshold = (-0.3, 2.0)
doppler_threshold = 0.1 # Disregard points with doppler < num

print(f"Processing file: {file_path}")
frames_data = process_log_file(file_path)

# Extract new dictionary with frame numbers and coordinates + Doppler
frames_data = extract_coordinates_with_doppler(frames_data, y_threshold, z_threshold, doppler_threshold)

"""
Having a legen of Cluster -1, means no cluster has been created
Same as having Grey Clusters
"""
create_interactive_plots(frames_data, x_limits=(-8, 8), y_limits=(0, 15), eps1=1.0, min_samples1=2, eps2=0.3, min_samples2=5, history_frames = 10)