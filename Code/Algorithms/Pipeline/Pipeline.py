import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.gridspec import GridSpec

import dataDecoderBrokenTimestamp
from frameAggregator import FrameAggregator
import pointFilter
import selfSpeedEstimator
from kalmanFilter import KalmanFilter
import veSpeedFilter


# -------------------------------
# Simulation parameters
# -------------------------------
#Defining the number of how many frames from the past should be used in the frame aggregator
# 0 = only current frame
# n = current frame + n previous frames
FRAME_AGGREGATOR_NUM_PAST_FRAMES = 9

#Defining a minimum SNR for the filter stage
FILTER_SNR_MIN = 12

#Defining minimum and maximum z for the filter stage
FILTER_Z_MIN = 0.3
FILTER_Z_MAX = 100

#Defining minimum and maximum phi for the filter stage
FILTER_PHI_MIN = -85
FILTER_PHI_MAX = 85

#Defining the self-speed's Kalman filter process variance and measurement variance
KALMAN_FILTER_PROCESS_VARIANCE = 0.01
KALMAN_FILTER_MEASUREMENT_VARIANCE = 0.1



# -------------------------------
# FUNCTION: Updating the simulation when the value of the slider has changed
# -------------------------------
self_speed_raw_history = []
self_speed_filtered_history = []
def update_sim(new_num_frame):
    global curr_num_frame
    global self_speed_raw_history
    global self_speed_filtered_history
    
    #Checking if new frame is earlier than the current processed frame (--> simulation needs to be rebuild until this particular frame)
    if new_num_frame < curr_num_frame:
            ##Clearing the pipeline
            #Clearing the frame aggregator
            frame_aggregator.clearBuffer()

            #Resetting the Kalman filter
            self_speed_kf.clear()
            

            ##Clearing the history variables
            self_speed_raw_history.clear()
            self_speed_filtered_history.clear()

            #Setting the current frame to -1 to start feeding at index 0
            curr_num_frame = -1
    
    #Simulating the necessary frames
    for num_frame in range(curr_num_frame + 1, new_num_frame + 1, 1):
        ##Feeding the pipeline
        #Getting the current frame
        frame = frames[num_frame]

        #Updating the frame aggregator
        frame_aggregator.updateBuffer(frame)

        #Getting the current point cloud frum the frame aggregator
        point_cloud = frame_aggregator.getPoints()

        #Filtering by SNR
        point_cloud_filtered = pointFilter.filterSNRmin(point_cloud, FILTER_SNR_MIN)

        #Filtering by z
        point_cloud_filtered = pointFilter.filterCartesianZ(point_cloud_filtered, FILTER_Z_MIN, FILTER_Z_MAX)

        #Filtering by phi
        point_cloud_filtered = pointFilter.filterSphericalPhi(point_cloud_filtered, FILTER_PHI_MIN, FILTER_PHI_MAX)

        #Estimating the self-speed
        self_speed_raw = selfSpeedEstimator.estimate_self_speed(point_cloud_filtered)

        #Kalman filtering the self-speed
        self_speed_filtered = self_speed_kf.update(self_speed_raw)

        #Calculating ve for all points (used for filtering afterwards)
        point_cloud_ve = veSpeedFilter.calculateVe(point_cloud_filtered)

        #Filtering points by ve
        point_cloud_ve_filtered = veSpeedFilter.filterPointsWithVe(point_cloud_ve, self_speed_filtered)

        ##Feeding the histories for the self speed
        self_speed_raw_history.append(self_speed_raw)
        self_speed_filtered_history.append(self_speed_filtered)

    #Updating the graphs
    update_graphs(point_cloud_ve_filtered, self_speed_raw_history, self_speed_filtered_history)

    #Updating the current frame number to the new last processed frame
    curr_num_frame = new_num_frame



# -------------------------------
# FUNCTION: Updating the simulation's graphs
# -------------------------------
def update_graphs(points, self_speed_raw_history, self_speed_filtered_history):
    global frames
    
    ##Plotting the points in the 3D plot
    #Creating arrays of the x,y,z coordinates
    points_x = np.array([point["x"] for point in points])
    points_y = np.array([point["y"] for point in points])
    points_z = np.array([point["z"] for point in points])

    #Clearing the plot and plotting the points in the 3D plot
    plot1.clear()
    plot1.set_xlabel('X [m]')
    plot1.set_ylabel('Y [m]')
    plot1.set_zlabel('Z [m]')
    plot1.set_xlim(-10, 10)
    plot1.set_ylim(0, 15)
    plot1.set_zlim(-0.30, 10)
    plot1.scatter(points_x, points_y, points_z)

    #Plotting the raw and filtered self-speed
    plot2.clear()
    plot2.set_xlim(0, len(frames))
    plot2.set_ylim(-3, 0)
    plot2.plot(np.arange(0, len(self_speed_raw_history)), np.array(self_speed_raw_history), linestyle='--')
    plot2.plot(np.arange(0, len(self_speed_filtered_history)), np.array(self_speed_filtered_history))



# -------------------------------
# Program entry point
# -------------------------------

##Getting the data
#Creating an absolute path to the raw data from a relative path
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.abspath(os.path.join(script_dir, "../../../Logs/LogsPart3/DynamicMonitoring/30fps_straight_3x3_log_2024-12-16.csv"))

#Reading in the frames
frames = dataDecoderBrokenTimestamp.decodeData(log_file)


##Creating the pipeline's objects
#Creating the frame aggregator
frame_aggregator = FrameAggregator(FRAME_AGGREGATOR_NUM_PAST_FRAMES)

#Creating the Kalman filter for the self-speed esimation
self_speed_kf = KalmanFilter(process_variance=KALMAN_FILTER_PROCESS_VARIANCE, measurement_variance=KALMAN_FILTER_MEASUREMENT_VARIANCE)


##Setting up the visualization and starting the simulation
#Creating a figure of size 10x10
fig = plt.figure(figsize=(10, 10))

#Defining a 2x1 grid layout
gs = GridSpec(2, 1, figure=fig)
plot1 = fig.add_subplot(gs[0, 0], projection='3d')
plot2 = fig.add_subplot(gs[1, 0])

#Setting the initial view angle of the 3D-plot to top-down
plot1.view_init(elev=90, azim=-90)

#Variable to hold the number of the latest frame that was processed successfully
curr_num_frame = -1

#Creating a slider for frame selection and attaching a handler to the on_changed event
ax_slider = plt.axes([0.2, 0.01, 0.65, 0.03])
slider = Slider(ax_slider, 'Frame', 0, len(frames) - 1, valinit=0, valstep=1)
slider.on_changed(update_sim)


##Starting the simulation with the first frame and showing the plot
update_sim(0)
plt.show()