import os
import pandas as pd
import struct
import math

# Parse Frame Header
def parse_frame_header(raw_data_list):
    if len(raw_data_list) < 40:
        raise ValueError("Insufficient data for Frame Header")
    raw_bytes = bytes([raw_data_list.pop(0) for _ in range(40)])
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
def parse_tlv_header(raw_data_list):
    if len(raw_data_list) < 8:
        raise ValueError("Insufficient data for TLV Header")
    raw_bytes = bytes([raw_data_list.pop(0) for _ in range(8)])
    tlv_type, tlv_length = struct.unpack('<II', raw_bytes)
    return {"TLV Type": tlv_type, "TLV Length": tlv_length}

# Parse Type 1: Detected Points
def parse_type_1_data(tlv_header, raw_data_list):
    """Parses Type 1 TLV payload (Detected Points)."""
    payload_length = tlv_header["TLV Length"]
    point_size = 16  # Each point has 16 bytes: X, Y, Z, Doppler
    num_points = payload_length // point_size

    detected_points = []
    for _ in range(num_points):
        if len(raw_data_list) < point_size:
            print("Warning: Insufficient data for Type 1 point.")
            break
        point_bytes = bytes([raw_data_list.pop(0) for _ in range(point_size)])
        x, y, z, doppler = struct.unpack('<ffff', point_bytes)

        # Calculate range profile from x, y, z
        comp_detected_range = math.sqrt((x * x) + (y * y) + (z * z))

        # Calculate azimuth from x, y
        if y == 0:
            detected_azimuth = 90 if x >= 0 else -90
        else:
            detected_azimuth = math.atan(x / y) * (180 / math.pi)

        # Calculate elevation angle from x, y, z
        if x == 0 and y == 0:
            detected_elev_angle = 90 if z >= 0 else -90
        else:
            detected_elev_angle = math.atan(z / math.sqrt((x * x) + (y * y))) * (180 / math.pi)

        # Append to detected points with additional info
        detected_points.append({
            "X [m]": x,
            "Y [m]": y,
            "Z [m]": z,
            "Doppler [m/s]": doppler,
            "Range [m]": comp_detected_range,
            "Azimuth [deg]": detected_azimuth,
            "Elevation Angle [deg]": detected_elev_angle
        })

    return {"Type 1 Data": detected_points}


# Parse Type 2: Placeholder for additional payloads
def parse_type_2_data(tlv_header, raw_data_list):
    payload_length = tlv_header["TLV Length"]
    payload = raw_data_list[:payload_length]
    raw_data_list[:payload_length] = []
    return {"Type 2 Data": payload}

# Parse Type 3: Another placeholder for raw data
def parse_type_3_data(tlv_header, raw_data_list):
    payload_length = tlv_header["TLV Length"]
    payload = raw_data_list[:payload_length]
    raw_data_list[:payload_length] = []
    return {"Type 3 Data": payload}

# Parse Type 7: Side Info (SNR and Noise)
def parse_type_7_data(tlv_header, raw_data_list, num_detected_obj):
    payload_length = tlv_header["TLV Length"]
    expected_length = 4 * num_detected_obj  # 4 bytes per point (2 SNR, 2 Noise)

    if payload_length != expected_length:
        print(f"Warning: Type 7 length mismatch. Expected {expected_length}, got {payload_length}.")
        raw_data_list[:payload_length] = []
        return {"Side Info": []}

    side_info = []
    for _ in range(num_detected_obj):
        if len(raw_data_list) < 4:
            #print("Warning: Insufficient data for Type 7 point.")
            break
        point_bytes = bytes([raw_data_list.pop(0) for _ in range(4)])
        snr, noise = struct.unpack('<HH', point_bytes)
        side_info.append({"SNR [dB]": snr * 0.1, "Noise [dB]": noise * 0.1})

    return {"Side Info": side_info}

# Process the log file
def process_log_file(file_path):
    frames_dict = {}
    data = pd.read_csv(file_path, names=["Timestamp", "RawData"], skiprows=1)

    for row_idx in range(len(data)):
        try:
            if pd.isnull(data.iloc[row_idx]['RawData']):
                print(f"Skipping row {row_idx + 1}: Null data.")
                continue

            raw_data_list = [int(x) for x in data.iloc[row_idx]['RawData'].split(',')]
            frame_header = parse_frame_header(raw_data_list)
            frame_number = frame_header["Frame Number"]

            frames_dict[frame_number] = {"Frame Header": frame_header, "TLVs": []}

            for _ in range(frame_header["Num TLVs"]):
                tlv_header = parse_tlv_header(raw_data_list)
                tlv_type = tlv_header["TLV Type"]

                if tlv_type == 1:
                    frames_dict[frame_number]["TLVs"].append(parse_type_1_data(tlv_header, raw_data_list))
                elif tlv_type == 2:
                    frames_dict[frame_number]["TLVs"].append(parse_type_2_data(tlv_header, raw_data_list))
                elif tlv_type == 3:
                    frames_dict[frame_number]["TLVs"].append(parse_type_3_data(tlv_header, raw_data_list))
                elif tlv_type == 7:
                    num_detected_obj = frame_header["Num Detected Obj"]
                    frames_dict[frame_number]["TLVs"].append(parse_type_7_data(tlv_header, raw_data_list, num_detected_obj))
                else:
                    print(f"Unknown TLV Type {tlv_type} in Frame {frame_number}. Skipping.")
                    raw_data_list[:tlv_header["TLV Length"]] = []

        except (ValueError, IndexError) as e:
            print(f"Error parsing row {row_idx + 1}: {e}")

    return frames_dict

# Main script
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    relative_path = os.path.join("..", "..", "..", "Logs", "LogsPart3", "StaticMonitoring", "Test_30fps_dist15mts_vehicleLog_5mps_d3x3wall_att1_log.csv")
    file_path = os.path.normpath(os.path.join(script_dir, relative_path))

    print(f"Processing file: {file_path}")
    frames_data = process_log_file(file_path)
    # Count total rows in the file (excluding header)
    total_rows = sum(1 for _ in open(file_path)) - 1
    # Print summary
    print(f"\nParsed {len(frames_data)} frames successfully out of {total_rows} total rows.")

    # Print sample data (first 5 frames) with limited decimal points
    for frame_num, frame_content in list(frames_data.items())[:5]:
        print(f"\nFrame {frame_num}:")
        for tlv in frame_content["TLVs"]:
            for key, value in tlv.items():
                if isinstance(value, list):  # For lists, print each item on a new line
                    print(f"  {key}:")
                    for item in value:
                        if isinstance(item, dict):  # If the item is a dictionary, limit decimals
                            formatted_item = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in item.items()}
                            print(f"    {formatted_item}")
                        else:
                            print(f"    {item}")
                else:  # For single key-value pairs, print inline
                    print(f"  {key}: {round(value, 3) if isinstance(value, float) else value}")


