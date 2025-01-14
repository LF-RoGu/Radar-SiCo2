import numpy as np
import matplotlib.pyplot as plt
import os

import dataDecoderBrokenTimestamp
import pointFilter
import selfSpeedEstimator
from kalmanFilter import KalmanFilter

#Defining the number of how many frames from the past should be used in estimation
# 0 = only current frame
# n = current frame + n previous frames
NUM_PAST_FRAMES = 2

#Initializing a figure for visualization
plt.ion()
fig, axes = plt.subplots(1, 1, figsize=(10, 6))
ax1 = axes

#Adding everything for kalman filtering the self speed
self_speed_history = []
kf_self_speed_history = []
kf_self_speed = KalmanFilter(process_variance=0.01, measurement_variance=0.1)
    
def update_self_speed_plot(self_speed_history, kf_self_speed_history):
    ax1.clear()
    ax1.set_xlim(0, 200)
    ax1.set_ylim(-5, 1)
    ax1.set_title("Re-calculated self-speed over time")
    ax1.set_xlabel("frame")
    ax1.set_ylabel("Self-speed (m/s)")

    #Creating a vector for the x axis
    x_vec = np.arange(len(self_speed_history))

    #Plotting raw self-speed
    ax1.plot(x_vec, self_speed_history, linestyle='--')

    #Plotting filtered self-speed
    ax1.plot(x_vec, kf_self_speed_history)


#Getting the data
script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.abspath(os.path.join(script_dir, "../../../../Logs/LogsPart3/DynamicMonitoring/30fps_straight_3x3_log_2024-12-16.csv"))
frames = dataDecoderBrokenTimestamp.decodeData(log_file)

#Processing frame by frame
for frm in range(len(frames)):
    #Getting the point cloud of the current frame
    point_cloud = frames[frm][1]
    #Appending the number of past frames to the point cloud
    for past_frm in range(max(0, frm - NUM_PAST_FRAMES), frm, 1):
        point_cloud = point_cloud + frames[past_frm][1]
    
    #Calculating the self speed
    #Filtering the input points
    filteredPointCloud = pointFilter.filterCartesianZ(point_cloud, 0, 3) #Filtering everything below 0 and above 3m
    filteredPointCloud = pointFilter.filterSphericalPhi(filteredPointCloud, -80, 80)
    self_speed = selfSpeedEstimator.estimate_self_speed(filteredPointCloud)
    self_speed_history.append(self_speed)

    #Kalman filtering the self speed
    filtered_self_speed = kf_self_speed.update(self_speed)
    kf_self_speed_history.append(filtered_self_speed)    

    update_self_speed_plot(self_speed_history, kf_self_speed_history)

    #Waiting
    plt.pause(0.01)

plt.ioff()
plt.show()