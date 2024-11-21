#include "IWR6843.h"

IWR6843::IWR6843()
{

}

int IWR6843::init(string configPort, string dataPort, string configFilePath)
{
	configPort_fd = open(configPort.c_str(), O_RDWR | O_NOCTTY | O_SYNC);
	if (configPort_fd < 1)
	{
		return -1;
	}
	if (configSerialPort(configPort_fd, B115200) < 1)
	{
		return -1;
	}

	dataPort_fd = open(dataPort.c_str(), O_RDONLY | O_NOCTTY | O_SYNC);
	if (dataPort_fd < 1)
	{
		return -1;
	}
	if (configSerialPort(dataPort_fd, B921600) < 1)
	{
		return -1;
	}

	if (sendConfigFile(configPort_fd, configFilePath) < 1)
	{
		return -1;
	}

	return 1;
}

int IWR6843::poll()
{
	//Checking if bytes are available
	int bytesAvailable = 0;
	if (ioctl(dataPort_fd, FIONREAD, &bytesAvailable) == -1)
	{
		return -1;
	}

	//Returning 0 if there are no bytes available
	if (bytesAvailable < 1)
	{
		return 0;
	}

	//Creating a temporary buffer and determining whether to read in the whole buffer or what is available (preventing overflow)
	uint8_t buffer[1024];
	int bytesToRead = min(bytesAvailable, (int)sizeof(buffer));

	//Reading bytes
	int bytesRead = read(dataPort_fd, buffer, bytesToRead);

	//Appending the read bytes to the end of the vector
	dataBuffer.insert(dataBuffer.end(), buffer, buffer + bytesRead);

	//Finding the indexes of the magic words (starting points of frames) in the buffer
	vector<size_t> indexesOfMagicWords = findIndexesOfMagicWord();

	//Returning 0 if size is below 2 (no full frame available)
	if (indexesOfMagicWords.size() < 2)
	{
		return 0;
	}

	//Deleting beginning of data until magic word if first index is unequal to 0 (garbage Data)
	if (indexesOfMagicWords.at(0) != 0)
	{
		dataBuffer.erase(dataBuffer.begin(), dataBuffer.begin() + indexesOfMagicWords.at(0));
	}

	//Extracting sublists containing one frame
	vector<vector<uint8_t>> sublists = splitIntoSublistsByIndexes(indexesOfMagicWords);

	//Iterating over the sublists and adding the decoded frames to the internal buffer
	for (uint8_t i = 0; i < sublists.size(); i++)
	{
		decodedFrameBuffer.push_back(SensorData(sublists.at(i)));
	}

	//Removing the elements of the dataBuffer that were processed
	dataBuffer.erase(dataBuffer.begin() + indexesOfMagicWords.front(), dataBuffer.begin() + indexesOfMagicWords.back());
	
	//Returning the amount of decoded frames
	return sublists.size();
}

vector<SensorData> IWR6843::getDecodedFrameBuffer()
{
	return decodedFrameBuffer;
}

vector<SensorData> IWR6843::getDecodedFramesFromTop(int num, bool del)
{
	vector<SensorData> framesFromTop(decodedFrameBuffer.begin(), decodedFrameBuffer.begin() + num);

	if (del)
	{
		decodedFrameBuffer.erase(decodedFrameBuffer.begin(), decodedFrameBuffer.begin() + num);
	}

	return framesFromTop;
}

int IWR6843::configSerialPort(int port_fd, int baudRate)
{
	struct termios tty;
	memset(&tty, 0, sizeof(tty));

	if (tcgetattr(port_fd, &tty) != 0)
	{
		return -1;
	}

	cfsetospeed(&tty, baudRate);
	cfsetispeed(&tty, baudRate);

	tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;     // 8-bit chars
	tty.c_iflag &= ~IGNBRK;                          // disable break processing
	tty.c_lflag = 0;                                 // no signaling chars, no echo
	tty.c_oflag = 0;                                 // no remapping, no delays
	tty.c_cc[VMIN] = 1;                             // read blocks until at least 1 char is available
	tty.c_cc[VTIME] = 5;                             // timeout in deciseconds for non-canonical read

	tty.c_iflag &= ~(IXON | IXOFF | IXANY);          // turn off s/w flow control
	tty.c_cflag |= (CLOCAL | CREAD);                 // ignore modem controls, enable reading
	tty.c_cflag &= ~(PARENB | PARODD);               // shut off parity
	tty.c_cflag &= ~CSTOPB;                          // 1 stop bit
	tty.c_cflag &= ~CRTSCTS;                         // no hardware flow control

	if (tcsetattr(port_fd, TCSANOW, &tty) != 0)
	{
		return -1;
	}

	return 1;
}

int IWR6843::sendConfigFile(int port_fd, string configFilePath)
{
	ifstream configFileStream(configFilePath);
	if (!configFileStream)
	{
		return -1;
	}
	
	string configFileLine;
	while (getline(configFileStream, configFileLine))
	{
		if (configFileLine.empty() || configFileLine[0] == '%')
		{
			continue;
		}

		//configFileLine += "\n\r";
		write(port_fd, configFileLine.c_str(), configFileLine.size());

		string response;
		do
		{
			//Checking the response's content
			if (response.find("Done") != string::npos || response.find("Skipped") != string::npos)
			{
				break;
			}

			//Checking if bytes are available te read from the serial port
			int bytesAvailable = 0;
			if (ioctl(port_fd, FIONREAD, &bytesAvailable) == -1)
			{
				return -1;
			}

			//Continuing if no bytes are available
			if (bytesAvailable == 0)
			{
				continue;
			}

			//Creating a temporary buffer and determining whether to read in the whole buffer or what is available (preventing overflow)
			char buffer[1024];
			int bytesToRead = min(bytesAvailable, (int)sizeof(buffer));

			//Reading the data in
			int bytesRead = read(port_fd, buffer, bytesToRead);
			response.append(buffer, bytesRead);
		} while (true);
	}

	return 1;
}


vector<size_t> IWR6843::findIndexesOfMagicWord()
{
	const vector<uint8_t> pattern = { 0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07 };
	
	std::vector<size_t> indexes;
	auto it = dataBuffer.begin();
	while ((it = search(it, dataBuffer.end(), pattern.begin(), pattern.end())) != dataBuffer.end())
	{
		indexes.push_back(distance(dataBuffer.begin(), it));
		++it;
	}

	return indexes;
}


vector<vector<uint8_t>> IWR6843::splitIntoSublistsByIndexes(const vector<size_t>& indexes)
{
	//Preparing a return vector
	vector<vector<uint8_t>> sublists;

	//Looping through all but the last index to form sublists between consecutive indexes
	for (size_t i = 0; i < indexes.size() - 1; ++i) {
		size_t start = indexes[i];
		size_t end = indexes[i + 1];

		//Creating a sublist from dataBuffer[start] to dataBuffer[end-1] and pushing it into return vector
		vector<uint8_t> sublist(dataBuffer.begin() + start, dataBuffer.begin() + end - 1);
		sublists.push_back(sublist);
	}

	return sublists;
}